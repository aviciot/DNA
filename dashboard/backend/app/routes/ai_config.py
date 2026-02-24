"""
AI Configuration Admin API
===========================
Read/write ai_prompts table and surface provider config info.
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_db_pool
from ..config import settings
from ..auth import require_admin

router = APIRouter(prefix="/api/v1/admin/ai-config", tags=["AI Config"])
logger = logging.getLogger(__name__)


class PromptRow(BaseModel):
    id: UUID
    prompt_key: str
    description: Optional[str]
    model: str
    max_tokens: int
    temperature: float
    is_active: bool
    prompt_text: str
    updated_at: datetime


class PromptUpdate(BaseModel):
    model: str
    max_tokens: int
    temperature: float
    is_active: bool
    prompt_text: str
    description: Optional[str] = None


class ProviderInfo(BaseModel):
    provider: str
    gemini_model: str
    anthropic_model: str
    groq_model: str
    has_gemini_key: bool
    has_anthropic_key: bool
    has_groq_key: bool
    worker_concurrency: int
    max_cost_per_task_usd: float


class ProviderUpdate(BaseModel):
    provider: str   # "gemini" | "anthropic" | "groq"
    model: str      # the model name for that provider


@router.get("/providers", response_model=ProviderInfo)
async def get_provider_info(pool=Depends(get_db_pool), admin=Depends(require_admin)):
    """Return current AI provider configuration.
    Reads env vars (which mirror ai-service config) + DB overrides from ai_settings."""
    # Check DB for any saved overrides
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT value FROM {settings.DATABASE_APP_SCHEMA}.ai_settings WHERE key = 'active_provider' LIMIT 1"
        )
        model_row = await conn.fetchrow(
            f"SELECT value FROM {settings.DATABASE_APP_SCHEMA}.ai_settings WHERE key = 'active_model' LIMIT 1"
        )

    provider = (row["value"] if row else None) or getattr(settings, "LLM_PROVIDER", "gemini")
    saved_model = model_row["value"] if model_row else None

    gemini_model = (saved_model if provider == "gemini" else None) or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    anthropic_model = (saved_model if provider == "anthropic" else None) or getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    groq_model = (saved_model if provider == "groq" else None) or getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")

    return ProviderInfo(
        provider=provider,
        gemini_model=gemini_model,
        anthropic_model=anthropic_model,
        groq_model=groq_model,
        has_gemini_key=bool(getattr(settings, "GOOGLE_API_KEY", "")),
        has_anthropic_key=bool(getattr(settings, "ANTHROPIC_API_KEY", "")),
        has_groq_key=bool(getattr(settings, "GROQ_API_KEY", "")),
        worker_concurrency=getattr(settings, "WORKER_CONCURRENCY", 3),
        max_cost_per_task_usd=getattr(settings, "MAX_COST_PER_TASK_USD", 5.0),
    )


@router.put("/providers", response_model=ProviderInfo)
async def update_provider(
    body: ProviderUpdate,
    pool=Depends(get_db_pool),
    admin=Depends(require_admin),
):
    """Save active provider + model to DB (ai_settings table).
    The ai-service worker reads these on next task."""
    if body.provider not in ("gemini", "anthropic", "groq"):
        raise HTTPException(400, "provider must be gemini, anthropic, or groq")

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_settings (key, value, updated_at)
            VALUES ('active_provider', $1, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            body.provider,
        )
        await conn.execute(
            f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_settings (key, value, updated_at)
            VALUES ('active_model', $1, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            body.model,
        )

    logger.info(f"Provider updated to {body.provider}/{body.model} by admin {admin.get('user_id')}")
    return await get_provider_info(pool=pool, admin=admin)


@router.get("/prompts", response_model=List[PromptRow])
async def list_prompts(admin=Depends(require_admin)):
    """List all AI prompts."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, prompt_key, description, model, max_tokens, temperature, is_active, prompt_text, updated_at "
            f"FROM {settings.DATABASE_APP_SCHEMA}.ai_prompts ORDER BY prompt_key"
        )
    return [dict(r) for r in rows]


@router.put("/prompts/{prompt_key}", response_model=PromptRow)
async def update_prompt(
    prompt_key: str,
    body: PromptUpdate,
    admin=Depends(require_admin),
):
    """Update an AI prompt configuration."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.ai_prompts
            SET model=$1, max_tokens=$2, temperature=$3, is_active=$4,
                prompt_text=$5, description=$6, updated_at=NOW()
            WHERE prompt_key=$7
            RETURNING id, prompt_key, description, model, max_tokens, temperature,
                      is_active, prompt_text, updated_at
            """,
            body.model, body.max_tokens, body.temperature, body.is_active,
            body.prompt_text, body.description, prompt_key,
        )
    if not row:
        raise HTTPException(404, f"Prompt '{prompt_key}' not found")
    logger.info(f"Prompt '{prompt_key}' updated by admin {admin.get('user_id')}")
    return dict(row)
