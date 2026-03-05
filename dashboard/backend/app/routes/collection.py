"""
Collection API
==============
Interview interface: grouped questions + answer upsert + evidence upload + template customization.
"""

import logging
import json
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

from ..database import get_db_pool
from ..auth import get_current_user, require_operator
from ..config import settings
from ..ws_manager import broadcast_notification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/customers", tags=["Collection"])

STATUS_PENDING  = "pending"
STATUS_ANSWERED = "answered"
STATUS_APPROVED = "completed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AnswerUpsert(BaseModel):
    field_key: str
    value: Any
    display_label: Optional[str] = None


class BulkAnswerUpsert(BaseModel):
    answers: List[AnswerUpsert]
    plan_id: Optional[UUID] = None


class SectionUpdate(BaseModel):
    section_id: str
    title: Optional[str] = None
    question: Optional[str] = None
    hint: Optional[str] = None
    example_value: Optional[str] = None
    is_mandatory: Optional[bool] = None
    requires_evidence: Optional[bool] = None
    evidence_description: Optional[str] = None


class TemplateCustomization(BaseModel):
    sections_update: Optional[List[SectionUpdate]] = None
    sections_add: Optional[List[dict]] = None
    sections_remove: Optional[List[str]] = None
    reorder: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(val):
    if isinstance(val, str):
        return json.loads(val)
    return val or {}


async def _get_user_name(conn, user_id: int) -> str:
    row = await conn.fetchrow(
        "SELECT full_name, email FROM auth.users WHERE id = $1", user_id
    )
    return (row["full_name"] or row["email"]) if row else str(user_id)


async def _get_customer_name(conn, customer_id: int) -> str:
    row = await conn.fetchrow(
        f"SELECT name FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1", customer_id
    )
    return row["name"] if row else str(customer_id)


async def _notify(conn, customer_id: int, type: str, title: str, message: str,
                  severity: str = "info", task_id=None, by_name: str = None):
    customer_name = await _get_customer_name(conn, customer_id)
    notif = await conn.fetchrow(f"""
        INSERT INTO {settings.DATABASE_APP_SCHEMA}.notifications
            (type, severity, title, message, customer_id, customer_name, task_id, created_by_name)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, type, severity, title, message, customer_id, customer_name,
                  task_id, created_by_name, created_at
    """, type, severity, title, message, customer_id, customer_name, task_id, by_name)

    await broadcast_notification({
        "id": str(notif["id"]),
        "type": notif["type"],
        "severity": notif["severity"],
        "title": notif["title"],
        "message": notif["message"],
        "customer_id": customer_id,
        "customer_name": customer_name,
        "task_id": str(task_id) if task_id else None,
        "created_by_name": by_name,
        "timestamp": int(notif["created_at"].timestamp() * 1000),
    })


async def _resolve_document_names(conn, template_ids: list, customer_id: int) -> list:
    if not template_ids:
        return []
    rows = await conn.fetch(f"""
        SELECT id, document_name
        FROM {settings.DATABASE_APP_SCHEMA}.customer_documents
        WHERE customer_id = $1 AND template_id = ANY($2::uuid[])
    """, customer_id, template_ids)
    return [{"doc_id": str(r["id"]), "document_name": r["document_name"]} for r in rows]


# ---------------------------------------------------------------------------
# GET /customers/{id}/plans/{plan_id}/questions
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/plans/{plan_id}/questions")
async def get_plan_questions(
    customer_id: int,
    plan_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT
                cp.id, cp.placeholder_key, cp.display_label, cp.question,
                cp.category, cp.hint, cp.example_value, cp.status,
                cp.is_required, cp.template_ids,
                cpd.field_value, cpd.source, cpd.verified,
                cpd.filled_by_name, cpd.filled_via, cpd.filled_at,
                ct.id          AS task_id,
                ct.status      AS task_status,
                ct.approved_at,
                ct.approved_by_name
            FROM {settings.DATABASE_APP_SCHEMA}.customer_placeholders cp
            LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_profile_data cpd
                ON cpd.customer_id = cp.customer_id AND cpd.field_key = cp.placeholder_key
            LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                ON ct.customer_id = cp.customer_id AND ct.plan_id = cp.plan_id
                AND ct.placeholder_key = cp.placeholder_key AND ct.requires_evidence = false
            WHERE cp.customer_id = $1 AND cp.plan_id = $2
            ORDER BY cp.category, cp.display_label
        """, customer_id, plan_id)

        grouped: dict = {}
        for row in rows:
            cat = row["category"] or "General"
            if cat not in grouped:
                grouped[cat] = {"category": cat, "questions": [], "evidence_tasks": [],
                                "total": 0, "answered": 0}
            q = dict(row)
            q["template_ids"] = [str(t) for t in (row["template_ids"] or [])]
            q["documents"] = await _resolve_document_names(conn, row["template_ids"] or [], customer_id)
            q["template_count"] = len(q["template_ids"])
            q["filled_at"] = row["filled_at"].isoformat() if row["filled_at"] else None
            q["task_id"] = str(row["task_id"]) if row["task_id"] else None
            q["task_status"] = row["task_status"]
            q["approved_at"] = row["approved_at"].isoformat() if row["approved_at"] else None
            q["approved_by_name"] = row["approved_by_name"]
            grouped[cat]["questions"].append(q)
            grouped[cat]["total"] += 1
            if row["task_status"] == STATUS_APPROVED:
                grouped[cat]["answered"] += 1

        ev_rows = await conn.fetch(f"""
            SELECT
                ct.id, ct.title, ct.description, ct.status,
                ct.evidence_description, ct.evidence_uploaded,
                ct.evidence_files, ct.answer_file_path,
                ct.answered_by_name, ct.answered_via, ct.answered_at,
                ct.approved_at, ct.approved_by_name,
                ct.document_id, cd.document_name, ct.placeholder_key
            FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
            LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents cd ON cd.id = ct.document_id
            WHERE ct.customer_id = $1 AND ct.plan_id = $2
              AND ct.requires_evidence = true AND ct.is_ignored = false
            ORDER BY ct.created_at
        """, customer_id, plan_id)

        ph_category = {r["placeholder_key"]: (r["category"] or "General") for r in rows}

        for ev in ev_rows:
            cat = ph_category.get(ev["placeholder_key"], "General")
            if cat not in grouped:
                grouped[cat] = {"category": cat, "questions": [], "evidence_tasks": [],
                                "total": 0, "answered": 0}
            et = dict(ev)
            et["id"] = str(ev["id"])
            et["document_id"] = str(ev["document_id"]) if ev["document_id"] else None
            et["answered_at"] = ev["answered_at"].isoformat() if ev["answered_at"] else None
            et["approved_at"] = ev["approved_at"].isoformat() if ev["approved_at"] else None
            et["approved_by_name"] = ev["approved_by_name"]
            grouped[cat]["evidence_tasks"].append(et)
            grouped[cat]["total"] += 1
            if ev["status"] == STATUS_APPROVED:
                grouped[cat]["answered"] += 1

        total = sum(g["total"] for g in grouped.values())
        answered = sum(g["answered"] for g in grouped.values())

        return {
            "plan_id": str(plan_id),
            "customer_id": customer_id,
            "total": total,
            "answered": answered,
            "completion_pct": round(answered / total * 100) if total else 0,
            "categories": list(grouped.values())
        }


# ---------------------------------------------------------------------------
# PUT /customers/{id}/profile
# ---------------------------------------------------------------------------

@router.put("/{customer_id}/profile")
async def upsert_profile_answers(
    customer_id: int,
    payload: BulkAnswerUpsert,
    current_user: dict = Depends(require_operator)
):
    pool = await get_db_pool()
    user_id = current_user.get("user_id")

    async with pool.acquire() as conn:
        user_name = await _get_user_name(conn, user_id)
        now = datetime.utcnow()
        updated = []

        for ans in payload.answers:
            value_str = ans.value if isinstance(ans.value, str) else json.dumps(ans.value)

            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_profile_data
                    (customer_id, field_key, field_value, display_label,
                     source, verified, confidence,
                     filled_by_user_id, filled_by_name, filled_via, filled_at)
                VALUES ($1, $2, $3, $4, 'dashboard', false, 100, $5, $6, 'dashboard', $7)
                ON CONFLICT (customer_id, field_key) DO UPDATE SET
                    field_value       = EXCLUDED.field_value,
                    display_label     = COALESCE(EXCLUDED.display_label, customer_profile_data.display_label),
                    source            = 'dashboard',
                    verified          = false,
                    filled_by_user_id = EXCLUDED.filled_by_user_id,
                    filled_by_name    = EXCLUDED.filled_by_name,
                    filled_via        = 'dashboard',
                    filled_at         = EXCLUDED.filled_at,
                    updated_at        = NOW()
            """, customer_id, ans.field_key, value_str, ans.display_label,
                user_id, user_name, now)

            await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                SET status = 'collected', updated_at = NOW()
                WHERE customer_id = $1 AND placeholder_key = $2
                  AND ($3::uuid IS NULL OR plan_id = $3)
            """, customer_id, ans.field_key, payload.plan_id)

            await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET status = '{STATUS_ANSWERED}',
                    answer = $3, answered_at = $4,
                    answered_by_user_id = $5, answered_by_name = $6,
                    answered_via = 'dashboard', updated_at = NOW()
                WHERE customer_id = $1 AND placeholder_key = $2
                  AND ($7::uuid IS NULL OR plan_id = $7)
                  AND status NOT IN ('{STATUS_ANSWERED}', '{STATUS_APPROVED}')
            """, customer_id, ans.field_key, value_str, now,
                user_id, user_name, payload.plan_id)

            docs = await conn.fetch(f"""
                SELECT id, placeholder_fill_status, content
                FROM {settings.DATABASE_APP_SCHEMA}.customer_documents
                WHERE customer_id = $1 AND placeholder_fill_status ? $2
            """, customer_id, ans.field_key)

            for doc in docs:
                fill_status = _parse_json(doc["placeholder_fill_status"])
                fill_status[ans.field_key] = "filled"
                total_keys = len(fill_status)
                filled_count = sum(1 for v in fill_status.values() if v == "filled")
                pct = round(filled_count / total_keys * 100) if total_keys else 0

                content = _parse_json(doc["content"])
                for section in content.get("fillable_sections", []):
                    key = (section.get("placeholder") or "").strip("{}")
                    if key == ans.field_key:
                        section["content"] = value_str
                        section["filled_at"] = now.isoformat()
                        section["filled_by"] = user_name

                await conn.execute(f"""
                    UPDATE {settings.DATABASE_APP_SCHEMA}.customer_documents
                    SET placeholder_fill_status = $1,
                        completion_percentage    = $2,
                        content                  = $3,
                        status = CASE WHEN $2 = 100 THEN 'completed'
                                      WHEN $2 > 0   THEN 'in_progress'
                                      ELSE status END,
                        updated_at = NOW()
                    WHERE id = $4
                """, json.dumps(fill_status), pct, json.dumps(content), doc["id"])

            updated.append(ans.field_key)

        return {"updated": updated, "count": len(updated)}


# ---------------------------------------------------------------------------
# POST /customers/{id}/tasks/{task_id}/evidence
# ---------------------------------------------------------------------------

@router.post("/{customer_id}/tasks/{task_id}/evidence")
async def upload_evidence(
    customer_id: int,
    task_id: UUID,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_operator)
):
    pool = await get_db_pool()
    user_id = current_user.get("user_id")

    async with pool.acquire() as conn:
        customer = await conn.fetchrow(f"""
            SELECT storage_path, name FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1
        """, customer_id)
        if not customer:
            raise HTTPException(404, "Customer not found")

        task = await conn.fetchrow(f"""
            SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
            WHERE id = $1 AND customer_id = $2
        """, task_id, customer_id)
        if not task:
            raise HTTPException(404, "Task not found")

        storage_path = customer["storage_path"] or f"/app/storage/customers/{customer_id}"
        evidence_dir = Path(storage_path) / "evidence" / str(task_id)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(file.filename).name
        file_path = evidence_dir / safe_filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        user_name = await _get_user_name(conn, user_id)
        customer_name = customer["name"]
        now = datetime.utcnow()
        relative_path = str(file_path)

        await conn.execute(f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
            SET evidence_uploaded    = true,
                answer_file_path     = $2,
                evidence_files       = jsonb_build_array(
                    jsonb_build_object(
                        'filename', $3::text,
                        'path', $2::varchar,
                        'size', $4::bigint,
                        'uploaded_at', $5::timestamp,
                        'uploaded_by', $6::text
                    )
                ),
                status               = '{STATUS_ANSWERED}',
                answered_at          = $5,
                answered_by_user_id  = $7,
                answered_by_name     = $6,
                answered_via         = 'dashboard',
                updated_at           = NOW()
            WHERE id = $1
        """, task_id, relative_path, safe_filename, len(content),
            now, user_name, user_id)

        await _notify(conn, customer_id, "evidence.uploaded", "Evidence Uploaded",
                      f"{user_name} uploaded evidence for {customer_name}: {safe_filename}",
                      severity="info", task_id=task_id, by_name=user_name)

        return {
            "task_id": str(task_id),
            "filename": safe_filename,
            "path": relative_path,
            "size": len(content),
            "uploaded_by": user_name,
            "uploaded_at": now.isoformat()
        }


# ---------------------------------------------------------------------------
# PUT /customers/{id}/documents/{doc_id}/template
# ---------------------------------------------------------------------------

@router.put("/{customer_id}/documents/{doc_id}/template")
async def customize_document_template(
    customer_id: int,
    doc_id: UUID,
    payload: TemplateCustomization,
    current_user: dict = Depends(require_operator)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"""
            SELECT id, content, placeholder_fill_status
            FROM {settings.DATABASE_APP_SCHEMA}.customer_documents
            WHERE id = $1 AND customer_id = $2
        """, doc_id, customer_id)
        if not row:
            raise HTTPException(404, "Document not found")

        content = _parse_json(row["content"])
        sections = content.get("fillable_sections", [])

        if payload.sections_remove:
            remove_set = set(payload.sections_remove)
            sections = [s for s in sections if s.get("id") not in remove_set]

        if payload.sections_update:
            update_map = {u.section_id: u for u in payload.sections_update}
            for section in sections:
                upd = update_map.get(section.get("id"))
                if upd:
                    for field in ["title", "question", "hint", "example_value",
                                  "is_mandatory", "requires_evidence", "evidence_description"]:
                        val = getattr(upd, field)
                        if val is not None:
                            section[field] = val

        if payload.sections_add:
            sections.extend(payload.sections_add)

        if payload.reorder:
            order_map = {sid: i for i, sid in enumerate(payload.reorder)}
            sections.sort(key=lambda s: order_map.get(s.get("id"), 9999))

        content["fillable_sections"] = sections
        fill_status = _parse_json(row["placeholder_fill_status"])
        for s in sections:
            key = (s.get("placeholder") or "").strip("{}")
            if key and key not in fill_status:
                fill_status[key] = "pending"

        total = len(fill_status)
        filled = sum(1 for v in fill_status.values() if v == "filled")
        pct = round(filled / total * 100) if total else 0

        await conn.execute(f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_documents
            SET content = $1, placeholder_fill_status = $2,
                completion_percentage = $3, updated_at = NOW()
            WHERE id = $4
        """, json.dumps(content), json.dumps(fill_status), pct, doc_id)

        return {"doc_id": str(doc_id), "sections_count": len(sections), "completion_pct": pct}


# ---------------------------------------------------------------------------
# POST /customers/{id}/tasks/{task_id}/approve
# ---------------------------------------------------------------------------

@router.post("/{customer_id}/tasks/{task_id}/approve")
async def approve_task(
    customer_id: int,
    task_id: UUID,
    current_user: dict = Depends(require_operator)
):
    pool = await get_db_pool()
    user_id = current_user.get("user_id")

    async with pool.acquire() as conn:
        user_name = await _get_user_name(conn, user_id)
        customer_name = await _get_customer_name(conn, customer_id)
        now = datetime.utcnow()

        result = await conn.execute(f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
            SET status              = '{STATUS_APPROVED}',
                approved_at         = $2,
                approved_by_user_id = $3,
                approved_by_name    = $4,
                completed_at        = $2,
                completed_by        = $3,
                updated_at          = NOW()
            WHERE id = $1 AND customer_id = $5
              AND status = '{STATUS_ANSWERED}'
        """, task_id, now, user_id, user_name, customer_id)

        if result == "UPDATE 0":
            raise HTTPException(400, "Task not found or not in answered state")

        await conn.execute(f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_placeholders
            SET status = 'collected', updated_at = NOW()
            WHERE customer_id = $1 AND placeholder_key = (
                SELECT placeholder_key FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
                WHERE id = $2
            )
        """, customer_id, task_id)

        await _notify(conn, customer_id, "task.approved", "Task Approved",
                      f"{user_name} approved a task for {customer_name}",
                      severity="info", task_id=task_id, by_name=user_name)

        return {"task_id": str(task_id), "approved_by": user_name, "approved_at": now.isoformat()}


# ---------------------------------------------------------------------------
# POST /customers/{id}/tasks/{task_id}/reopen
# ---------------------------------------------------------------------------

@router.post("/{customer_id}/tasks/{task_id}/reopen")
async def reopen_task(
    customer_id: int,
    task_id: UUID,
    current_user: dict = Depends(require_operator)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        customer_name = await _get_customer_name(conn, customer_id)

        result = await conn.execute(f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
            SET status              = '{STATUS_ANSWERED}',
                approved_at         = NULL,
                approved_by_user_id = NULL,
                approved_by_name    = NULL,
                completed_at        = NULL,
                completed_by        = NULL,
                updated_at          = NOW()
            WHERE id = $1 AND customer_id = $2
              AND status = '{STATUS_APPROVED}'
        """, task_id, customer_id)

        if result == "UPDATE 0":
            raise HTTPException(400, "Task not found or not in approved state")

        await _notify(conn, customer_id, "task.reopened", "Task Reopened for Edit",
                      f"A task for {customer_name} was reopened for editing",
                      severity="warning", task_id=task_id, by_name=None)

        return {"task_id": str(task_id), "status": STATUS_ANSWERED}
