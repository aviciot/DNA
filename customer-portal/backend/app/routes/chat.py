import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Cookie
from app.config import settings
from app.db import get_pool

logger = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT = """You are a helpful ISO compliance assistant for a customer self-service portal.
You help customers understand what information they need to provide for their ISO certification.
You can see their pending questions and progress. Be concise, friendly, and practical.
Never make up compliance requirements — only explain what's in the customer's actual task list.
If asked to submit an answer, confirm the value with the customer first.
Use the available tools to look up tasks, progress, and document details when relevant."""

MAX_TOOL_ROUNDS = 5


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


async def _get_pending_summary(customer_id: int, plan_id: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT title, placeholder_key, status
                FROM {settings.database_app_schema}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2
                  AND is_ignored = false AND status NOT IN ('cancelled', 'completed')
                ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 ELSE 3 END
                LIMIT 20""",
            customer_id, plan_id,
        )
    if not rows:
        return "All tasks are complete."
    lines = [f"- {r['title']} (key: {r['placeholder_key']}, status: {r['status']})" for r in rows]
    return "Pending tasks:\n" + "\n".join(lines)


async def _get_llm_config() -> dict | None:
    """Fetch active portal_chat LLM config from DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT lp.name, lp.api_key,
                       COALESCE(
                           (SELECT value FROM {settings.database_app_schema}.ai_settings WHERE key = 'portal_chat_model'),
                           lp.available_models->>0
                       ) AS model
                FROM {settings.database_app_schema}.llm_providers lp
                JOIN {settings.database_app_schema}.ai_settings ais
                    ON ais.key = 'portal_chat_provider' AND ais.value = lp.name
                WHERE lp.enabled = true
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
        async with Client(mcp_endpoint) as client:
            tools = await client.list_tools()

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
    """Call an MCP tool, injecting portal_token server-side."""
    try:
        from fastmcp import Client
        mcp_endpoint = f"{settings.mcp_url}/mcp"
        async with Client(mcp_endpoint) as client:
            result = await client.call_tool(name, {**arguments, "token": portal_token})
        # CallToolResult has a .content list of content items
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
        logger.error(f"MCP tool '{name}' error: {e}")
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


async def _stream_final(llm_config: dict, messages: list, tools: list, ws: WebSocket, portal_token: str) -> str:
    """
    Run the agentic tool-call loop, then stream the final text response.
    Returns the full assistant reply.
    """
    provider = llm_config["provider"]
    model = llm_config["model"]
    api_key = llm_config["api_key"]
    reply = ""

    try:
        if provider in ("openai", "groq"):
            from openai import AsyncOpenAI
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key) if provider == "groq" else AsyncOpenAI(api_key=api_key)

            # Tool-call resolution (non-streaming)
            if tools:
                messages = await _agentic_loop_openai(client, model, messages, tools, portal_token)

            # Stream final response
            stream = await client.chat.completions.create(
                model=model, messages=messages, max_tokens=1024, temperature=0.3, stream=True
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    reply += delta
                    await ws.send_json({"type": "token", "content": delta})

        elif provider == "anthropic":
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

        else:  # gemini — no native tool streaming; run directly
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
            user_text = messages[-1]["content"] if messages else ""
            response = await m.generate_content_async(user_text, stream=True)
            async for chunk in response:
                for part in (chunk.candidates[0].content.parts if chunk.candidates else []):
                    if getattr(part, "thought", False):
                        continue
                    text = getattr(part, "text", "") or ""
                    if text:
                        reply += text
                        await ws.send_json({"type": "token", "content": text})

        await ws.send_json({"type": "done"})

    except Exception as e:
        logger.error(f"LLM stream error ({provider}): {e}")
        await ws.send_json({"type": "error", "content": str(e)})

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

    # Fetch MCP tools once per session (cached in memory for this WS connection)
    mcp_tools = await _fetch_mcp_tools()

    # Read max_context_messages from DB
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg_row = await conn.fetchrow(
            f"""SELECT config_value FROM {settings.database_app_schema}.customer_configuration
                WHERE customer_id IS NULL AND config_type = 'mcp_chat'
                  AND config_key = 'max_context_messages' AND is_active = true
                LIMIT 1"""
        )
    try:
        max_ctx = int(json.loads(cfg_row["config_value"])) if cfg_row else 20
    except Exception:
        max_ctx = 20

    pending_summary = await _get_pending_summary(session["customer_id"], str(session["plan_id"]))
    context = (
        f"Customer: {session['customer_name']}\n"
        f"ISO Standard: {session['iso_code']} — {session['iso_name']}\n"
        f"{pending_summary}"
    )
    if mcp_tools:
        context += f"\n\nYou have {len(mcp_tools)} tools available to look up live data."

    system_msg = {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context}"}
    history = []

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            user_msg = (data.get("message") or "").strip()
            if not user_msg:
                continue

            history.append({"role": "user", "content": user_msg})
            messages = [system_msg] + history[-max_ctx:]
            reply = await _stream_final(llm_config, messages, mcp_tools, websocket, portal_token)
            if reply:
                history.append({"role": "assistant", "content": reply})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Chat WS error: {e}")
