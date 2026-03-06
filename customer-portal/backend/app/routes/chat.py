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
If asked to submit an answer, confirm the value with the customer first."""


async def _get_session(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT ecr.token, ecr.customer_id, ecr.plan_id,
                       c.name AS customer_name, iso.code AS iso_code, iso.name AS iso_name
                FROM {settings.database_app_schema}.email_collection_requests ecr
                JOIN {settings.database_app_schema}.customers c ON c.id = ecr.customer_id
                JOIN {settings.database_app_schema}.customer_iso_plans cip ON cip.id = ecr.plan_id
                JOIN {settings.database_app_schema}.iso_standards iso ON iso.id = cip.iso_standard_id
                WHERE ecr.token = $1 AND ecr.status != 'cancelled' AND ecr.expires_at > NOW()""",
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


async def _stream_llm(messages: list, ws: WebSocket):
    """Stream LLM response tokens to WebSocket. Uses groq by default, falls back to any available."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT name, model, api_key FROM {settings.database_app_schema}.llm_providers
                WHERE enabled = true ORDER BY is_default_chat DESC, name LIMIT 1"""
        )

    if not row or not row["api_key"]:
        await ws.send_json({"type": "error", "content": "No LLM provider configured"})
        return

    import base64, hashlib
    from cryptography.fernet import Fernet
    raw = row["api_key"]
    if raw.startswith("enc:"):
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
        api_key = Fernet(key).decrypt(raw[4:].encode()).decode()
    else:
        api_key = raw

    provider = row["name"]
    model = row["model"]

    try:
        if provider == "groq":
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key)
            stream = await client.chat.completions.create(
                model=model, messages=messages, max_tokens=1024,
                temperature=0.3, stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    await ws.send_json({"type": "token", "content": delta})

        elif provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            system = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_msgs = [m for m in messages if m["role"] != "system"]
            async with client.messages.stream(
                model=model, max_tokens=1024, system=system, messages=user_msgs,
            ) as stream:
                async for text in stream.text_stream:
                    await ws.send_json({"type": "token", "content": text})

        else:  # gemini
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
            user_text = messages[-1]["content"] if messages else ""
            response = await m.generate_content_async(user_text, stream=True)
            async for chunk in response:
                if chunk.text:
                    await ws.send_json({"type": "token", "content": chunk.text})

        await ws.send_json({"type": "done"})

    except Exception as e:
        logger.error(f"LLM stream error ({provider}): {e}")
        await ws.send_json({"type": "error", "content": str(e)})


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

    pending_summary = await _get_pending_summary(session["customer_id"], str(session["plan_id"]))
    context = (
        f"Customer: {session['customer_name']}\n"
        f"ISO Standard: {session['iso_code']} — {session['iso_name']}\n"
        f"{pending_summary}"
    )
    history = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context}"}]

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            user_msg = (data.get("message") or "").strip()
            if not user_msg:
                continue

            history.append({"role": "user", "content": user_msg})
            await _stream_llm(history[-10:], websocket)  # keep last 10 turns

            # Capture assistant reply for history (reconstruct from tokens not practical here,
            # so we just note the turn happened — full history tracking is a v2 feature)
            history.append({"role": "assistant", "content": "[streamed]"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Chat WS error: {e}")
