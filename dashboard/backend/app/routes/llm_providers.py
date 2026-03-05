"""
LLM Providers Admin API
========================
Central place to configure provider API keys + models.
Keys are Fernet-encrypted before storage (same pattern as automation credentials).

GET  /api/v1/admin/llm-providers          — list all providers (keys masked)
PUT  /api/v1/admin/llm-providers/{name}   — update key / model / enabled
POST /api/v1/admin/llm-providers/{name}/test — live connectivity test
"""
import base64
import hashlib
import logging
from typing import Optional

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_admin
from ..config import settings
from ..database import get_db_pool

router = APIRouter(prefix="/api/v1/admin/llm-providers", tags=["LLM Providers"])
logger = logging.getLogger(__name__)

_ENC_PREFIX = "enc:"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def _encrypt(value: str) -> str:
    if not value or value.startswith(_ENC_PREFIX):
        return value
    return _ENC_PREFIX + _fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except Exception:
        return ""


class ProviderUpdate(BaseModel):
    api_key: Optional[str] = None   # None = don't change; "••••••••" = don't change
    model: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("")
async def list_providers(pool=Depends(get_db_pool), _=Depends(require_admin)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, name, display_name, model, enabled, "
            f"(api_key IS NOT NULL AND api_key != '') AS has_key "
            f"FROM {settings.DATABASE_APP_SCHEMA}.llm_providers ORDER BY name"
        )
    return [dict(r) for r in rows]


@router.put("/{name}")
async def update_provider(
    name: str,
    body: ProviderUpdate,
    pool=Depends(get_db_pool),
    _=Depends(require_admin),
):
    updates, values, i = [], [], 1

    if body.api_key and body.api_key != "••••••••":
        updates.append(f"api_key = ${i}"); values.append(_encrypt(body.api_key)); i += 1
    if body.model is not None:
        updates.append(f"model = ${i}"); values.append(body.model); i += 1
    if body.enabled is not None:
        updates.append(f"enabled = ${i}"); values.append(body.enabled); i += 1

    if not updates:
        raise HTTPException(400, "Nothing to update")

    updates.append("updated_at = NOW()")
    values.append(name)

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE {settings.DATABASE_APP_SCHEMA}.llm_providers "
            f"SET {', '.join(updates)} WHERE name = ${i}",
            *values,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, f"Provider '{name}' not found")

    logger.info(f"llm_providers[{name}] updated")
    return {"ok": True}


@router.post("/{name}/test")
async def test_provider(
    name: str,
    pool=Depends(get_db_pool),
    _=Depends(require_admin),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT api_key, model FROM {settings.DATABASE_APP_SCHEMA}.llm_providers WHERE name = $1",
            name,
        )
    if not row:
        raise HTTPException(404, f"Provider '{name}' not found")

    key = _decrypt(row["api_key"] or "")
    if not key:
        return {"ok": False, "message": "API key not configured"}

    try:
        if name == "anthropic":
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
                          "messages": [{"role": "user", "content": "Hi"}]},
                )
            if r.status_code == 200:
                return {"ok": True, "message": f"Anthropic key valid — {row['model']} reachable"}
            return {"ok": False, "message": f"Anthropic {r.status_code}: {r.json().get('error',{}).get('message','')}"}

        elif name == "groq":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 200:
                count = len(r.json().get("data", []))
                return {"ok": True, "message": f"Groq key valid — {count} models available"}
            return {"ok": False, "message": f"Groq {r.status_code}: {r.text[:200]}"}

        else:  # gemini
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                )
            if r.status_code == 200:
                count = len(r.json().get("models", []))
                return {"ok": True, "message": f"Google key valid — {count} models available"}
            return {"ok": False, "message": f"Google {r.status_code}: {r.json().get('error',{}).get('message','')}"}

    except Exception as e:
        return {"ok": False, "message": str(e)}
