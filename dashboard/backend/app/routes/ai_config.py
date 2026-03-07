"""
AI Configuration Admin API
===========================
GET  /api/v1/admin/ai-config/providers           — list per-service AI config
PUT  /api/v1/admin/ai-config/providers           — upsert one service row
GET  /api/v1/admin/ai-config/prompts             — list AI prompts
PUT  /api/v1/admin/ai-config/prompts/{key}       — update a prompt
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

VALID_SERVICES = {"iso_builder", "extraction", "portal_chat"}


# ──────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────

class AIServiceConfig(BaseModel):
    service: str
    provider: str
    model: str
    updated_at: Optional[datetime] = None


class AIServiceUpdate(BaseModel):
    service: str    # 'iso_builder' | 'extraction'
    provider: str   # must match llm_providers.name
    model: str


class PromptRow(BaseModel):
    id: UUID
    prompt_key: str
    description: Optional[str]
    is_active: bool
    prompt_text: str
    updated_at: datetime


class PromptUpdate(BaseModel):
    is_active: bool
    prompt_text: str
    description: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# Service AI config (provider + model per service)
# ──────────────────────────────────────────────────────────────

@router.get("/providers", response_model=List[AIServiceConfig])
async def get_ai_config(pool=Depends(get_db_pool), admin=Depends(require_admin)):
    """Return per-service AI configuration (provider + model for each service)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT service, provider, model, updated_at"
            f" FROM {settings.DATABASE_APP_SCHEMA}.ai_config ORDER BY service"
        )
    return [dict(r) for r in rows]


@router.put("/providers", response_model=List[AIServiceConfig])
async def update_ai_config(
    body: AIServiceUpdate,
    pool=Depends(get_db_pool),
    admin=Depends(require_admin),
):
    """Upsert provider + model for one service."""
    if body.service not in VALID_SERVICES:
        raise HTTPException(400, f"service must be one of: {', '.join(sorted(VALID_SERVICES))}")

    async with pool.acquire() as conn:
        # Verify provider exists
        exists = await conn.fetchval(
            f"SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.llm_providers WHERE name = $1",
            body.provider,
        )
        if not exists:
            raise HTTPException(400, f"Unknown provider '{body.provider}'")

        await conn.execute(
            f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_config (service, provider, model, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (service) DO UPDATE
                SET provider   = EXCLUDED.provider,
                    model      = EXCLUDED.model,
                    updated_at = NOW()
            """,
            body.service, body.provider, body.model,
        )

    logger.info(
        f"ai_config updated: service={body.service} provider={body.provider} "
        f"model={body.model} by admin {admin.get('user_id')}"
    )
    return await get_ai_config(pool=pool, admin=admin)


# ──────────────────────────────────────────────────────────────
# Prompt templates
# ──────────────────────────────────────────────────────────────

@router.get("/prompts", response_model=List[PromptRow])
async def list_prompts(admin=Depends(require_admin)):
    """List all AI prompts."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, prompt_key, description, is_active, prompt_text, updated_at "
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
            SET is_active=$1, prompt_text=$2, description=$3, updated_at=NOW()
            WHERE prompt_key=$4
            RETURNING id, prompt_key, description, is_active, prompt_text, updated_at
            """,
            body.is_active, body.prompt_text, body.description, prompt_key,
        )
    if not row:
        raise HTTPException(404, f"Prompt '{prompt_key}' not found")
    logger.info(f"Prompt '{prompt_key}' updated by admin {admin.get('user_id')}")
    return dict(row)
