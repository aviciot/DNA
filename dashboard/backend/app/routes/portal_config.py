"""
Portal Configuration API
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/portal-config", tags=["Portal Config"])

SCHEMA = "dna_app"


# ── Models ────────────────────────────────────────────────────

class ChatDefaults(BaseModel):
    language: str
    chat_tone: str
    max_context_messages: int
    max_tokens: int


class PortalSettings(BaseModel):
    token_expiry_days: int
    require_av_scan: bool
    max_upload_mb: int


# ── Helpers ───────────────────────────────────────────────────

async def _get_mcp_defaults(conn) -> dict:
    rows = await conn.fetch(
        f"""SELECT config_key, config_value FROM {SCHEMA}.customer_configuration
            WHERE customer_id IS NULL AND config_type = 'mcp_chat' AND is_active = true"""
    )
    return {r["config_key"]: r["config_value"] for r in rows}


async def _get_portal_settings(conn) -> dict:
    rows = await conn.fetch(
        f"""SELECT config_key, config_value FROM {SCHEMA}.customer_configuration
            WHERE customer_id IS NULL AND config_type = 'portal_settings' AND is_active = true"""
    )
    return {r["config_key"]: r["config_value"] for r in rows}


async def _upsert_config(conn, config_type: str, key: str, value, user_id: int):
    await conn.execute(
        f"""INSERT INTO {SCHEMA}.customer_configuration
                (customer_id, config_type, config_key, config_value, is_default, created_by, updated_by)
            VALUES (NULL, $1, $2, $3::jsonb, true, $4, $4)
            ON CONFLICT (customer_id, config_type, config_key)
            DO UPDATE SET config_value = EXCLUDED.config_value, updated_by = $4, updated_at = NOW()""",
        config_type, key, f'"{value}"' if isinstance(value, str) else str(value).lower() if isinstance(value, bool) else str(value),
        user_id,
    )


# ── Endpoints ─────────────────────────────────────────────────

@router.get("")
async def get_portal_config(user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        mcp = await _get_mcp_defaults(conn)
        settings = await _get_portal_settings(conn)

        # LLM provider for portal_chat
        provider_row = await conn.fetchrow(
            f"SELECT value FROM {SCHEMA}.ai_settings WHERE key = 'portal_chat_provider'"
        )
        model_row = await conn.fetchrow(
            f"SELECT value FROM {SCHEMA}.ai_settings WHERE key = 'portal_chat_model'"
        )

        # System prompt
        prompt_row = await conn.fetchrow(
            f"SELECT id, prompt_key, prompt_text, is_active, description, updated_at "
            f"FROM {SCHEMA}.ai_prompts WHERE prompt_key = 'portal_mcp_system'"
        )

    return {
        "chat_defaults": {
            "language": (mcp.get("language") or {}).get("value", mcp.get("language", "en")) if isinstance(mcp.get("language"), dict) else mcp.get("language", "en"),
            "chat_tone": (mcp.get("chat_tone") or {}).get("value", mcp.get("chat_tone", "friendly")) if isinstance(mcp.get("chat_tone"), dict) else mcp.get("chat_tone", "friendly"),
            "max_context_messages": int((mcp.get("max_context_messages") or {}).get("value", mcp.get("max_context_messages", 20))) if isinstance(mcp.get("max_context_messages"), dict) else int(mcp.get("max_context_messages", 20)),
            "max_tokens": int((mcp.get("max_tokens") or {}).get("value", mcp.get("max_tokens", 8192))) if isinstance(mcp.get("max_tokens"), dict) else int(mcp.get("max_tokens", 8192)),
        },
        "portal_settings": {
            "token_expiry_days": int((settings.get("token_expiry_days") or {}).get("value", settings.get("token_expiry_days", 30))) if isinstance(settings.get("token_expiry_days"), dict) else int(settings.get("token_expiry_days", 30)),
            "require_av_scan": bool((settings.get("require_av_scan") or {}).get("value", settings.get("require_av_scan", True))) if isinstance(settings.get("require_av_scan"), dict) else bool(settings.get("require_av_scan", True)),
            "max_upload_mb": int((settings.get("max_upload_mb") or {}).get("value", settings.get("max_upload_mb", 10))) if isinstance(settings.get("max_upload_mb"), dict) else int(settings.get("max_upload_mb", 10)),
        },
        "llm": {
            "provider": provider_row["value"] if provider_row else "",
            "model": model_row["value"] if model_row else "",
        },
        "system_prompt": dict(prompt_row) if prompt_row else None,
    }


@router.put("/chat-defaults")
async def update_chat_defaults(body: ChatDefaults, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    uid = user.get("user_id")
    async with pool.acquire() as conn:
        await _upsert_config(conn, "mcp_chat", "language", body.language, uid)
        await _upsert_config(conn, "mcp_chat", "chat_tone", body.chat_tone, uid)
        await _upsert_config(conn, "mcp_chat", "max_context_messages", body.max_context_messages, uid)
        await _upsert_config(conn, "mcp_chat", "max_tokens", body.max_tokens, uid)
    return {"ok": True}


@router.put("/settings")
async def update_portal_settings(body: PortalSettings, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    uid = user.get("user_id")
    async with pool.acquire() as conn:
        await _upsert_config(conn, "portal_settings", "token_expiry_days", body.token_expiry_days, uid)
        await _upsert_config(conn, "portal_settings", "require_av_scan", body.require_av_scan, uid)
        await _upsert_config(conn, "portal_settings", "max_upload_mb", body.max_upload_mb, uid)
    return {"ok": True}


@router.get("/stats")
async def get_portal_stats(user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        active_tokens = await conn.fetchval(
            f"SELECT COUNT(*) FROM {SCHEMA}.email_collection_requests "
            f"WHERE status != 'cancelled' AND expires_at > NOW()"
        ) or 0

        portal_logins = await conn.fetchval(
            f"SELECT COUNT(*) FROM {SCHEMA}.portal_activity_log WHERE event = 'token_validated'"
        ) or 0

        answers_submitted = await conn.fetchval(
            f"SELECT COUNT(*) FROM {SCHEMA}.portal_activity_log WHERE event = 'answer_submitted'"
        ) or 0

        mcp_usage = await conn.fetchrow(
            f"""SELECT COUNT(*) AS calls,
                       COALESCE(SUM(cost_usd), 0) AS total_cost
                FROM {SCHEMA}.ai_usage_log
                WHERE operation_type LIKE 'portal_chat:%'"""
        )

    return {
        "active_tokens": active_tokens,
        "portal_logins": portal_logins,
        "answers_submitted": answers_submitted,
        "mcp_chat_calls": mcp_usage["calls"] if mcp_usage else 0,
        "mcp_chat_cost_usd": float(mcp_usage["total_cost"]) if mcp_usage else 0.0,
    }
