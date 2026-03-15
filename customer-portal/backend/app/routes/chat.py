import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Cookie
from app.config import settings
from app.db import get_pool
logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TOOL_ROUNDS = 5

_DEFAULT_SYSTEM_PROMPT = (
    "You are an ISO compliance assistant in a customer portal chat widget. "
    "Help customers understand and complete their certification tasks. "
    "Use **bold** for key terms, short bullet lists, max 2 emojis per response. "
    "Keep answers concise and scannable."
)


async def _get_cost_rates(provider: str) -> dict:
    """Return cost_per_1k_input/output for this provider (or zeros if not set)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT cost_per_1k_input, cost_per_1k_output "
                f"FROM {settings.database_app_schema}.llm_providers WHERE name = $1",
                provider,
            )
        return dict(row) if row else {}
    except Exception:
        return {}


async def _get_system_prompt() -> str:
    """Load portal chat system prompt from DB; fall back to default."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT prompt_text FROM {settings.database_app_schema}.ai_prompts "
                "WHERE prompt_key = 'portal_mcp_system' AND is_active = true LIMIT 1"
            )
        return row["prompt_text"] if row else _DEFAULT_SYSTEM_PROMPT
    except Exception as e:
        logger.warning(f"Could not load system prompt from DB: {e}")
        return _DEFAULT_SYSTEM_PROMPT


async def _get_session(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT cpa.token, cpa.customer_id,
                       c.name AS customer_name,
                       cip.id AS plan_id, iso.code AS iso_code, iso.name AS iso_name
                FROM {settings.database_app_schema}.customer_portal_access cpa
                JOIN {settings.database_app_schema}.customers c ON c.id = cpa.customer_id
                LEFT JOIN {settings.database_app_schema}.customer_iso_plans cip
                    ON cip.customer_id = cpa.customer_id
                LEFT JOIN {settings.database_app_schema}.iso_standards iso ON iso.id = cip.iso_standard_id
                WHERE cpa.token = $1 AND cpa.expires_at > NOW()
                ORDER BY cip.created_at LIMIT 1""",
            token,
        )
    return dict(row) if row else None


async def _get_pending_summary(customer_id: int, plan_id) -> str:
    if not plan_id:
        return ""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT title, status
                FROM {settings.database_app_schema}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2::uuid
                  AND is_ignored = false AND status NOT IN ('cancelled', 'completed')
                ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 ELSE 3 END
                LIMIT 5""",
            customer_id, str(plan_id),
        )
    if not rows:
        return "All tasks are complete."
    lines = [f"- {r['title']} ({r['status']})" for r in rows]
    return "Top pending tasks:\n" + "\n".join(lines)


async def _get_welcome_counts(customer_id: int, plan_id) -> dict:
    """Return open task counts by priority for the welcome message."""
    if not plan_id:
        return {"total": 0, "urgent": 0, "high": 0}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT priority FROM {settings.database_app_schema}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2::uuid
                  AND is_ignored = false AND status NOT IN ('cancelled', 'completed')""",
            customer_id, str(plan_id),
        )
    total = len(rows)
    urgent = sum(1 for r in rows if r["priority"] == "urgent")
    high = sum(1 for r in rows if r["priority"] == "high")
    return {"total": total, "urgent": urgent, "high": high}


async def _send_welcome(ws: WebSocket, session: dict, counts: dict) -> None:
    """Send a single welcome message with progress summary."""
    first_name = session["customer_name"].split()[0]
    iso = session.get("iso_code") or "ISO"
    total = counts["total"]
    urgent = counts["urgent"]
    high = counts["high"]

    if total == 0:
        status_line = "✅ **All tasks are complete** — great work!"
    else:
        flags = []
        if urgent:
            flags.append(f"**{urgent} urgent** ⚠️")
        if high:
            flags.append(f"**{high} high**")
        rest = total - urgent - high
        if rest:
            flags.append(f"{rest} normal")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        status_line = f"You have **{total} open {iso} task{'s' if total != 1 else ''}**{flag_str}."

    text = (
        f"Hi {first_name}! 👋 {status_line}\n\n"
        "Here's what I can help you with:\n"
        "- **Explain** any task — just ask \"what is [task name]?\"\n"
        "- **Show** your pending or urgent items\n"
        "- **Submit** an answer for a task directly from this chat\n\n"
        "What would you like to do?"
    )
    await ws.send_json({"type": "welcome", "content": text})


async def _get_llm_config() -> dict | None:
    """Fetch active portal_chat LLM config from DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT lp.name, lp.api_key,
                       COALESCE(ac.model, lp.available_models->>0) AS model
                FROM {settings.database_app_schema}.ai_config ac
                JOIN {settings.database_app_schema}.llm_providers lp ON lp.name = ac.provider
                WHERE ac.service = 'portal_chat' AND lp.enabled = true
                LIMIT 1"""
        )
        if not row:
            row = await conn.fetchrow(
                f"""SELECT name, api_key, available_models->>0 AS model
                    FROM {settings.database_app_schema}.llm_providers
                    WHERE enabled = true ORDER BY is_default_chat DESC LIMIT 1"""
            )
    if not row or not row["api_key"]:
        return None

    import base64, hashlib
    from cryptography.fernet import Fernet
    raw = row["api_key"]
    if raw.startswith("enc:"):
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
        api_key = Fernet(key).decrypt(raw[4:].encode()).decode()
    else:
        api_key = raw

    return {"provider": row["name"], "model": row["model"], "api_key": api_key}


# ── MCP helpers ──────────────────────────────────────────────────────────────

def _strip_token_param(schema: dict) -> dict:
    """Remove 'token' from tool input schema — injected server-side, never exposed to LLM."""
    if not schema:
        return schema
    props = schema.get("properties", {})
    required = schema.get("required", [])
    props = {k: v for k, v in props.items() if k != "token"}
    required = [r for r in required if r != "token"]
    return {**schema, "properties": props, "required": required}


async def _mcp_call_with_retry(coro_fn, retries: int = 3, base_delay: float = 0.5):
    """Run an async MCP call with exponential backoff retries."""
    last_exc = None
    for attempt in range(retries):
        try:
            return await coro_fn()
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
    raise last_exc


async def _fetch_mcp_tools() -> list[dict]:
    """
    Connect to MCP server and return tool list in OpenAI-compatible format.
    Token param is stripped — injected server-side on every tool call.
    Returns [] if MCP is disabled or unreachable.
    """
    if not settings.mcp_enabled:
        return []
    try:
        from fastmcp import Client
        mcp_endpoint = f"{settings.mcp_url}/mcp"

        async def _do():
            async with Client(mcp_endpoint) as client:
                return await client.list_tools()

        tools = await _mcp_call_with_retry(_do)
        result = []
        for t in tools:
            schema = _strip_token_param(t.inputSchema if hasattr(t, "inputSchema") else {})
            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": schema,
                },
            })
        logger.info(f"MCP: loaded {len(result)} tools from {settings.mcp_url}")
        return result
    except Exception as e:
        logger.warning(f"MCP unavailable — running without tools: {e}")
        return []


async def _call_mcp_tool(name: str, arguments: dict, portal_token: str) -> str:
    """Call an MCP tool with retry, injecting portal_token server-side."""
    try:
        from fastmcp import Client
        mcp_endpoint = f"{settings.mcp_url}/mcp"

        async def _do():
            async with Client(mcp_endpoint) as client:
                return await client.call_tool(name, {**arguments, "token": portal_token})

        result = await _mcp_call_with_retry(_do)
        items = result.content if hasattr(result, "content") else (result if isinstance(result, list) else [result])
        parts = []
        for item in items:
            if hasattr(item, "text"):
                parts.append(item.text)
            elif hasattr(item, "data"):
                parts.append(str(item.data))
            else:
                parts.append(str(item))
        return "\n".join(parts) or "(no result)"
    except Exception as e:
        logger.error(f"MCP tool '{name}' failed after retries: {e}")
        return f"Tool error: {e}"


# ── Agentic loop helpers (provider-specific) ─────────────────────────────────

def _tools_to_anthropic(openai_tools: list[dict]) -> list[dict]:
    """Convert OpenAI-format tools to Anthropic format."""
    result = []
    for t in openai_tools:
        fn = t["function"]
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


async def _agentic_loop_openai(client, model: str, messages: list, tools: list, portal_token: str) -> list:
    """Run tool-call rounds for OpenAI/Groq. Returns updated messages (no streaming)."""
    from openai.types.chat import ChatCompletionMessageToolCall
    for _ in range(MAX_TOOL_ROUNDS):
        kwargs = {"model": model, "messages": messages, "max_tokens": 1024, "temperature": 0.3}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break
        # Add assistant message with tool calls
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]})
        # Execute each tool call
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            tool_result = await _call_mcp_tool(tc.function.name, args, portal_token)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})
    return messages


async def _agentic_loop_anthropic(client, model: str, messages: list, system: str, tools: list, portal_token: str) -> list:
    """Run tool-call rounds for Anthropic. Returns updated messages (no streaming)."""
    for _ in range(MAX_TOOL_ROUNDS):
        kwargs = {"model": model, "max_tokens": 1024, "system": system, "messages": messages}
        if tools:
            kwargs["tools"] = _tools_to_anthropic(tools)
        resp = await client.messages.create(**kwargs)
        if resp.stop_reason != "tool_use":
            break
        # Collect tool use blocks
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for tu in tool_uses:
            tool_result = await _call_mcp_tool(tu.name, dict(tu.input), portal_token)
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": tool_result})
        messages.append({"role": "user", "content": tool_results})
    return messages


async def _check_budget(customer_id: int) -> tuple[float, float]:
    """
    Return (budget_usd, spent_this_month_usd) for the customer.
    budget_usd of 0 means no limit set.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            budget_row = await conn.fetchrow(
                f"SELECT monthly_llm_budget_usd FROM {settings.database_app_schema}.customers WHERE id = $1",
                customer_id,
            )
            spent_row = await conn.fetchrow(
                f"""SELECT COALESCE(SUM(cost_usd), 0) AS spent
                    FROM {settings.database_app_schema}.ai_usage_log
                    WHERE customer_id = $1
                      AND date_trunc('month', started_at) = date_trunc('month', NOW())""",
                customer_id,
            )
        budget = float(budget_row["monthly_llm_budget_usd"] or 0) if budget_row else 0.0
        spent = float(spent_row["spent"] or 0) if spent_row else 0.0
        return budget, spent
    except Exception as e:
        logger.warning(f"Budget check failed: {e}")
        return 0.0, 0.0


async def _log_usage(customer_id: int, provider: str, model: str,
                     tokens_in: int, tokens_out: int, cost_rates: dict,
                     started_at, duration_ms: int,
                     operation_type: str = "portal_chat") -> None:
    """Insert one row into ai_usage_log for a portal LLM call."""
    try:
        rate_in = float(cost_rates.get("cost_per_1k_input") or 0)
        rate_out = float(cost_rates.get("cost_per_1k_output") or 0)
        cost = (tokens_in / 1000 * rate_in) + (tokens_out / 1000 * rate_out)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {settings.database_app_schema}.ai_usage_log
                    (operation_type, provider, model, tokens_input, tokens_output,
                     cost_usd, duration_ms, status, customer_id, started_at, completed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'success', $8, $9, NOW())""",
                operation_type, provider, model, tokens_in, tokens_out, round(cost, 6),
                duration_ms, customer_id, started_at,
            )
    except Exception as e:
        logger.warning(f"Usage log failed: {e}")


async def _stream_final(llm_config: dict, messages: list, tools: list, ws: WebSocket,
                        portal_token: str, customer_id: int, cost_rates: dict) -> str:
    """
    Run the agentic tool-call loop, then stream the final text response.
    Returns the full assistant reply.
    """
    import datetime
    provider = llm_config["provider"]
    model = llm_config["model"]
    api_key = llm_config["api_key"]
    reply = ""
    tokens_in = tokens_out = 0
    started_at = datetime.datetime.now(datetime.timezone.utc)

    try:
        if provider in ("openai", "groq"):
            from openai import AsyncOpenAI
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key) if provider == "groq" else AsyncOpenAI(api_key=api_key)

            # Tool-call resolution (non-streaming)
            if tools:
                messages = await _agentic_loop_openai(client, model, messages, tools, portal_token)

            # Stream final response
            max_out = 512 if provider == "groq" else 1024
            stream_kwargs = dict(model=model, messages=messages, max_tokens=max_out, temperature=0.3, stream=True)
            if provider == "openai":
                stream_kwargs["stream_options"] = {"include_usage": True}
            stream = await client.chat.completions.create(**stream_kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or "" if chunk.choices else ""
                if delta:
                    reply += delta
                    await ws.send_json({"type": "token", "content": delta})
                if chunk.usage:
                    tokens_in = chunk.usage.prompt_tokens or 0
                    tokens_out = chunk.usage.completion_tokens or 0

        elif provider in ("anthropic", "claude"):
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            system = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_msgs = [m for m in messages if m["role"] != "system"]

            # Tool-call resolution (non-streaming)
            if tools:
                user_msgs = await _agentic_loop_anthropic(client, model, user_msgs, system, tools, portal_token)

            # Stream final response
            async with client.messages.stream(
                model=model, max_tokens=1024, system=system, messages=user_msgs
            ) as stream:
                async for text in stream.text_stream:
                    reply += text
                    await ws.send_json({"type": "token", "content": text})
                final = await stream.get_final_message()
                tokens_in = final.usage.input_tokens or 0
                tokens_out = final.usage.output_tokens or 0

        else:  # gemini
            from google import genai as _genai
            from google.genai import types as _genai_types
            _gclient = _genai.Client(api_key=api_key)
            system_prompt = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_text = messages[-1]["content"] if messages else ""
            async for chunk in await _gclient.aio.models.generate_content_stream(
                model=model,
                contents=user_text,
                config=_genai_types.GenerateContentConfig(system_instruction=system_prompt or None),
            ):
                text = chunk.text or ""
                if text:
                    reply += text
                    await ws.send_json({"type": "token", "content": text})
                if chunk.usage_metadata:
                    tokens_in = chunk.usage_metadata.prompt_token_count or 0
                    tokens_out = chunk.usage_metadata.candidates_token_count or 0

        await ws.send_json({"type": "done"})

    except Exception as e:
        logger.error(f"LLM stream error ({provider}): {e}")
        await ws.send_json({"type": "error", "content": str(e)})

    finally:
        duration_ms = int((datetime.datetime.now(datetime.timezone.utc) - started_at).total_seconds() * 1000)
        if tokens_in or tokens_out:
            await _log_usage(customer_id, provider, model, tokens_in, tokens_out,
                             cost_rates, started_at, duration_ms)

    return reply


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/chat")
async def portal_chat(websocket: WebSocket, portal_token: str = Cookie(None)):
    await websocket.accept()

    if not portal_token:
        await websocket.send_json({"type": "error", "content": "No session"})
        await websocket.close(code=4001)
        return

    session = await _get_session(portal_token)
    if not session:
        await websocket.send_json({"type": "error", "content": "Invalid or expired session"})
        await websocket.close(code=4001)
        return

    llm_config = await _get_llm_config()
    if not llm_config:
        await websocket.send_json({"type": "error", "content": "No LLM provider configured"})
        await websocket.close(code=4002)
        return

    # Fetch MCP tools, system prompt, cost rates, and config in parallel
    mcp_tools, system_prompt_text, cost_rates = await asyncio.gather(
        _fetch_mcp_tools(),
        _get_system_prompt(),
        _get_cost_rates(llm_config["provider"]),
    )

    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg_row = await conn.fetchrow(
            f"""SELECT config_value FROM {settings.database_app_schema}.customer_configuration
                WHERE customer_id IS NULL AND config_type = 'mcp_chat'
                  AND config_key = 'max_context_messages' AND is_active = true
                LIMIT 1"""
        )
    try:
        max_ctx = int(json.loads(cfg_row["config_value"])) if cfg_row else 6
    except Exception:
        max_ctx = 6

    pending_summary = await _get_pending_summary(session["customer_id"], session["plan_id"])
    context = (
        f"Customer: {session['customer_name']}\n"
        f"ISO Standard: {session['iso_code']} — {session['iso_name']}\n"
        f"{pending_summary}"
    )
    # Only mention tools if they actually loaded — prevents hallucinated tool calls
    if mcp_tools:
        context += f"\n\nYou have access to {len(mcp_tools)} tools: {', '.join(t['function']['name'] for t in mcp_tools)}."

    system_msg = {"role": "system", "content": f"{system_prompt_text}\n\nContext:\n{context}"}
    history = []

    # Send personalised welcome with live progress counts
    try:
        counts = await _get_welcome_counts(session["customer_id"], session["plan_id"])
        await _send_welcome(websocket, session, counts)
    except Exception as e:
        logger.warning(f"Welcome failed: {e}")
        try:
            await websocket.send_json({"type": "welcome", "content": "Hi! I'm your ISO compliance assistant. How can I help you today? 💡"})
        except Exception:
            pass

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            user_msg = (data.get("message") or "").strip()
            if not user_msg:
                continue

            # Budget guard — block if monthly limit exceeded
            budget, spent = await _check_budget(session["customer_id"])
            if budget > 0 and spent >= budget:
                await websocket.send_json({
                    "type": "error",
                    "content": (
                        f"Your organization has reached its monthly AI usage limit "
                        f"(${budget:.2f}). Please contact your administrator."
                    ),
                })
                await websocket.send_json({"type": "done"})
                continue

            history.append({"role": "user", "content": user_msg})
            messages = [system_msg] + history[-max_ctx:]
            reply = await _stream_final(
                llm_config, messages, mcp_tools, websocket,
                portal_token, session["customer_id"], cost_rates,
            )
            if reply:
                history.append({"role": "assistant", "content": reply})
            else:
                # LLM failed — drop the user message too so history stays clean
                history.pop()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Chat WS error: {e}")
