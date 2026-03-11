"""
ISO360 Templates API
====================
Manages platform-level ISO360 task/evidence templates derived from placeholder metadata.

Endpoints:
  GET  /api/v1/iso360-templates/standard/{iso_standard_id}          — list placeholders + template status
  POST /api/v1/iso360-templates/standard/{iso_standard_id}/generate — trigger LLM generation job
  GET  /api/v1/iso360-templates/jobs/{job_id}/status                — poll job status
  GET  /api/v1/iso360-templates/{template_id}                       — get single template
  PUT  /api/v1/iso360-templates/{template_id}                       — update template (inline edit)
"""
import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_db_pool
from ..config import settings
from ..auth import get_current_user, require_admin
from ..redis_client import get_redis

router = APIRouter(prefix="/api/v1/iso360-templates", tags=["ISO360 Templates"])
logger = logging.getLogger(__name__)

_SCHEMA = settings.DATABASE_APP_SCHEMA
_JOB_TTL = 3600  # 1 hour


# ── Models ───────────────────────────────────────────────────────

class ISO360TemplateUpdate(BaseModel):
    title: Optional[str] = None
    responsible_role: Optional[str] = None
    steps: Optional[list] = None
    evidence_fields: Optional[list] = None
    status: Optional[str] = None


# ── Redis job helpers ─────────────────────────────────────────────

async def _set_job_status(redis, job_id: str, data: dict):
    await redis._client.set(f"iso360_job:{job_id}", json.dumps(data), ex=_JOB_TTL)


async def _get_job_status(redis, job_id: str) -> dict | None:
    raw = await redis._client.get(f"iso360_job:{job_id}")
    return json.loads(raw) if raw else None


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/standard/{iso_standard_id}")
async def list_iso360_activities(
    iso_standard_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Return all recurring activities for the standard, enriched with iso360_template status.
    Primary source: recurring_activities per template + iso360_recurring_activities at ISO level.
    Falls back to placeholder_dictionary if standard hasn't been rebuilt yet.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        std_row = await conn.fetchrow(
            f"""SELECT id, code, name, placeholder_dictionary, iso360_recurring_activities
                FROM {_SCHEMA}.iso_standards WHERE id = $1""",
            iso_standard_id,
        )
        if not std_row:
            raise HTTPException(404, "ISO standard not found")

        # Per-template recurring activities
        tmpl_rows = await conn.fetch(
            f"""SELECT t.id, t.name, t.recurring_activities
                FROM {_SCHEMA}.templates t
                JOIN {_SCHEMA}.template_iso_mapping m ON m.template_id = t.id
                WHERE m.iso_standard_id = $1
                  AND t.recurring_activities IS NOT NULL
                  AND jsonb_array_length(COALESCE(t.recurring_activities, '[]'::jsonb)) > 0""",
            iso_standard_id,
        )

        # Existing iso360_templates for this standard
        template_rows = await conn.fetch(
            f"""SELECT t.placeholder_key, t.id, t.type, t.update_frequency, t.title,
                       t.responsible_role, t.status, t.updated_at,
                       (SELECT COUNT(*) FROM {_SCHEMA}.iso360_template_iso_mapping m2
                        WHERE m2.template_id = t.id) AS used_by_standards_count
                FROM {_SCHEMA}.iso360_templates t
                JOIN {_SCHEMA}.iso360_template_iso_mapping m ON m.template_id = t.id
                WHERE m.iso_standard_id = $1""",
            iso_standard_id,
        )

    template_by_key = {row["placeholder_key"]: dict(row) for row in template_rows}

    # Build activity list from new source
    seen_keys = set()
    activities = []

    def _enrich(act: dict, template_name: str | None, template_id: str | None, source: str):
        key = act.get("key")
        if not key or key in seen_keys:
            return
        seen_keys.add(key)
        tmpl = template_by_key.get(key)
        activities.append({
            **act,
            "template_name": template_name,
            "template_id_source": template_id,
            "source": source,
            # iso360_template status
            "template_status": tmpl["status"] if tmpl else "not_generated",
            "iso360_template_id": str(tmpl["id"]) if tmpl else None,
            "iso360_template_title": tmpl["title"] if tmpl else None,
            "used_by_standards_count": int(tmpl["used_by_standards_count"]) if tmpl else 0,
            "template_updated_at": tmpl["updated_at"].isoformat() if tmpl and tmpl.get("updated_at") else None,
        })

    # Per-template activities
    for row in tmpl_rows:
        raw = row["recurring_activities"]
        acts = json.loads(raw) if isinstance(raw, str) else (raw or [])
        for act in acts:
            if isinstance(act, dict):
                _enrich(act, row["name"], str(row["id"]), "template")

    # ISO-level cross-cutting
    raw_iso = std_row["iso360_recurring_activities"]
    iso_acts = json.loads(raw_iso) if isinstance(raw_iso, str) else (raw_iso or [])
    for act in iso_acts:
        if isinstance(act, dict):
            _enrich(act, None, None, "iso_level")

    has_recurring_activities = len(activities) > 0

    # Fallback to placeholder_dictionary if no recurring_activities yet
    if not has_recurring_activities:
        raw_dict = std_row["placeholder_dictionary"]
        placeholder_dict = json.loads(raw_dict) if isinstance(raw_dict, str) else (raw_dict or [])
        has_metadata = any(isinstance(e, dict) and "type" in e for e in placeholder_dict)
        for entry in placeholder_dict:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            tmpl = template_by_key.get(key)
            activities.append({
                **entry,
                "title": entry.get("label") or key,
                "iso_clause": entry.get("category", ""),
                "description": entry.get("question", ""),
                "template_name": None,
                "template_id_source": None,
                "source": "placeholder_fallback",
                "template_status": tmpl["status"] if tmpl else "not_generated",
                "iso360_template_id": str(tmpl["id"]) if tmpl else None,
                "iso360_template_title": tmpl["title"] if tmpl else None,
                "used_by_standards_count": int(tmpl["used_by_standards_count"]) if tmpl else 0,
                "template_updated_at": tmpl["updated_at"].isoformat() if tmpl and tmpl.get("updated_at") else None,
            })
    else:
        has_metadata = True  # recurring_activities present means standard was rebuilt with 024

    generated_count = sum(1 for a in activities if a.get("template_status") != "not_generated")
    recurring_acts = [a for a in activities if a.get("lifecycle") != "static"]

    return {
        "iso_standard_id": iso_standard_id,
        "iso_code": std_row["code"],
        "iso_name": std_row["name"],
        "has_metadata": has_metadata,
        "has_recurring_activities": has_recurring_activities,
        "activities": activities,
        "stats": {
            "total": len(activities),
            "recurring": len(recurring_acts),
            "generated": generated_count,
            "not_generated": len(recurring_acts) - generated_count,
        },
    }


@router.post("/standard/{iso_standard_id}/generate")
async def trigger_iso360_template_generation(
    iso_standard_id: str,
    user: dict = Depends(require_admin),
):
    """
    Trigger ISO360 template generation for all recurring placeholders
    that don't yet have a template. Returns a job_id to poll for status.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        std_row = await conn.fetchrow(
            f"SELECT id, code, name FROM {_SCHEMA}.iso_standards WHERE id = $1",
            iso_standard_id,
        )
    if not std_row:
        raise HTTPException(404, "ISO standard not found")

    job_id = uuid.uuid4().hex
    redis = await get_redis()

    await _set_job_status(redis, job_id, {
        "status": "queued",
        "progress": 0,
        "total": 0,
        "done": 0,
        "current_key": None,
        "iso_code": std_row["code"],
    })

    await redis.add_to_stream("automation:iso360_template", {
        "job_id": job_id,
        "iso_standard_id": iso_standard_id,
    })

    logger.info(f"ISO360 template generation queued: job={job_id}, standard={std_row['code']}")
    return {"job_id": job_id, "iso_code": std_row["code"], "status": "queued"}


@router.get("/jobs/{job_id}/status")
async def get_iso360_job_status(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """Poll the status of an ISO360 template generation job."""
    redis = await get_redis()
    status = await _get_job_status(redis, job_id)
    if not status:
        raise HTTPException(404, "Job not found or expired")
    return status


@router.get("/{template_id}")
async def get_iso360_template(
    template_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single ISO360 template with full details."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT t.*,
                       ARRAY_AGG(DISTINCT iso.code) FILTER (WHERE iso.code IS NOT NULL) AS iso_codes
                FROM {_SCHEMA}.iso360_templates t
                LEFT JOIN {_SCHEMA}.iso360_template_iso_mapping m ON m.template_id = t.id
                LEFT JOIN {_SCHEMA}.iso_standards iso ON iso.id = m.iso_standard_id
                WHERE t.id = $1
                GROUP BY t.id""",
            template_id,
        )
    if not row:
        raise HTTPException(404, "Template not found")

    result = dict(row)
    for field in ("steps", "evidence_fields"):
        if isinstance(result.get(field), str):
            try:
                result[field] = json.loads(result[field])
            except Exception:
                result[field] = []
    return result


@router.put("/{template_id}")
async def update_iso360_template(
    template_id: str,
    body: ISO360TemplateUpdate,
    user: dict = Depends(require_admin),
):
    """Update an ISO360 template (inline edit of steps, evidence fields, status, etc.)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            f"SELECT id FROM {_SCHEMA}.iso360_templates WHERE id = $1",
            template_id,
        )
        if not existing:
            raise HTTPException(404, "Template not found")

        updates = []
        params = [template_id]
        i = 2

        if body.title is not None:
            updates.append(f"title = ${i}"); params.append(body.title); i += 1
        if body.responsible_role is not None:
            updates.append(f"responsible_role = ${i}"); params.append(body.responsible_role); i += 1
        if body.steps is not None:
            updates.append(f"steps = ${i}::jsonb"); params.append(json.dumps(body.steps)); i += 1
        if body.evidence_fields is not None:
            updates.append(f"evidence_fields = ${i}::jsonb"); params.append(json.dumps(body.evidence_fields)); i += 1
        if body.status is not None:
            if body.status not in ("generated", "needs_review", "approved"):
                raise HTTPException(422, "Invalid status value")
            updates.append(f"status = ${i}"); params.append(body.status); i += 1

        if not updates:
            raise HTTPException(422, "No fields to update")

        updates.append("generated_by = 'manual'")
        updates.append("updated_at = NOW()")

        await conn.execute(
            f"UPDATE {_SCHEMA}.iso360_templates SET {', '.join(updates)} WHERE id = $1",
            *params,
        )

    return {"ok": True}
