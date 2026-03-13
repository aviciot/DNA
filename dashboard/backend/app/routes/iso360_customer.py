"""
ISO360 Customer Tab API
=======================
Returns all ISO360 activity data for a customer across all their enabled plans.

Endpoint:
  GET /api/v1/customers/{customer_id}/iso360
"""
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..auth import get_current_user
from ..config import settings
from ..database import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["iso360-customer"])

_SCHEMA = settings.DATABASE_APP_SCHEMA


# ── Pydantic models ───────────────────────────────────────────────────────────

class StepItem(BaseModel):
    order: int
    instruction: str


class EvidenceField(BaseModel):
    field_name: str
    field_type: str
    required: bool


class ISO360Activity(BaseModel):
    doc_id: str
    plan_id: str
    placeholder_key: str
    title: str
    type: str
    update_frequency: str
    responsible_role: Optional[str] = None
    iso_clause: Optional[str] = None
    status: str
    next_due_date: Optional[str] = None
    last_completed_at: Optional[str] = None
    steps: List[Dict[str, Any]] = []
    evidence_fields: List[Dict[str, Any]] = []
    completion_status: str
    excluded: bool = False


class ISO360PlanStats(BaseModel):
    total: int
    completed_this_year: int
    due_soon: int
    overdue: int
    event_based: int


class ISO360Plan(BaseModel):
    plan_id: str
    iso_code: str
    iso_name: str
    iso360_enabled: bool
    adjustment_pass_done: bool
    onboarding_threshold_pct: int
    activities: List[ISO360Activity] = []
    stats: ISO360PlanStats


class ISO360CustomerResponse(BaseModel):
    plans: List[ISO360Plan] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_jsonb(val: Any) -> Any:
    """Parse JSONB field that asyncpg may return as raw string."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            return val
    return val


def _compute_completion_status(
    update_frequency: str,
    next_due_date: Optional[date],
    last_completed_at: Optional[datetime],
    today: date,
) -> str:
    if update_frequency == "event_based" and next_due_date is None:
        return "event_based"

    if next_due_date is None:
        return "upcoming"

    # Normalize last_completed_at to date
    last_done: Optional[date] = None
    if last_completed_at is not None:
        if isinstance(last_completed_at, datetime):
            last_done = last_completed_at.date()
        else:
            last_done = last_completed_at  # type: ignore

    # Completed: last_done is set AND (next_due is in future OR no next_due)
    if last_done is not None and (next_due_date is None or next_due_date > today):
        return "completed"

    # Overdue: next_due < today AND not completed (or completed before next_due)
    if next_due_date < today:
        if last_done is None or last_done < next_due_date:
            return "overdue"
        # Completed after due date — treat as completed
        return "completed"

    # Due soon: within 30 days
    delta = (next_due_date - today).days
    if 0 <= delta <= 30:
        return "due_soon"

    return "upcoming"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/{customer_id}/iso360",
    response_model=ISO360CustomerResponse,
    summary="Get all ISO360 activity data for a customer",
)
async def get_customer_iso360(
    customer_id: int,
    user: dict = Depends(get_current_user),
):
    """
    Returns all ISO360 plans (where iso360_enabled=TRUE) for a customer,
    including activity records with completion status computed server-side.
    """
    pool = await get_db_pool()
    today = date.today()

    async with pool.acquire() as conn:
        # ── 1. Fetch enabled plans ────────────────────────────────────────────
        plan_rows = await conn.fetch(
            f"""
            SELECT
                p.id          AS plan_id,
                p.iso360_enabled,
                s.code        AS iso_code,
                s.name        AS iso_name,
                COALESCE(ps.adjustment_pass_done, FALSE)       AS adjustment_pass_done,
                COALESCE(ps.onboarding_threshold_pct, 70)      AS onboarding_threshold_pct
            FROM {_SCHEMA}.customer_iso_plans p
            JOIN {_SCHEMA}.iso_standards      s  ON s.id = p.iso_standard_id
            LEFT JOIN {_SCHEMA}.iso360_plan_settings ps ON ps.plan_id = p.id
            WHERE p.customer_id = $1
              AND p.iso360_enabled = TRUE
            ORDER BY s.code
            """,
            customer_id,
        )

        if not plan_rows:
            return ISO360CustomerResponse(plans=[])

        # ── 2. Fetch all ISO360 activity documents for this customer ──────────
        activity_rows = await conn.fetch(
            f"""
            SELECT
                cd.id                  AS doc_id,
                cd.plan_id,
                cd.document_name       AS title,
                cd.status,
                cd.next_due_date,
                cd.last_completed_at,
                cd.content,
                COALESCE(cd.excluded, FALSE) AS excluded,
                t.placeholder_key,
                t.type,
                t.update_frequency,
                t.responsible_role,
                COALESCE(
                    (SELECT (tim.covered_clauses)[1]
                     FROM {_SCHEMA}.iso360_template_iso_mapping tim
                     WHERE tim.template_id = t.id
                     LIMIT 1),
                    ''
                ) AS iso_clause
            FROM {_SCHEMA}.customer_documents   cd
            JOIN {_SCHEMA}.iso360_templates      t  ON t.id = cd.iso360_template_id
            WHERE cd.customer_id = $1
              AND cd.document_type = 'iso360_activity'
            ORDER BY cd.next_due_date NULLS LAST, t.type, t.placeholder_key
            """,
            customer_id,
        )

    # ── 3. Build plan map ─────────────────────────────────────────────────────
    plan_map: Dict[str, dict] = {}
    for row in plan_rows:
        pid = str(row["plan_id"])
        plan_map[pid] = {
            "plan_id": pid,
            "iso_code": row["iso_code"],
            "iso_name": row["iso_name"],
            "iso360_enabled": row["iso360_enabled"],
            "adjustment_pass_done": row["adjustment_pass_done"],
            "onboarding_threshold_pct": row["onboarding_threshold_pct"],
            "activities": [],
        }

    # ── 4. Process activity rows ──────────────────────────────────────────────
    current_year = today.year

    for row in activity_rows:
        pid = str(row["plan_id"])
        if pid not in plan_map:
            continue  # activity belongs to a plan that is not ISO360-enabled

        content = _parse_jsonb(row["content"]) or {}

        # iso_clause: prefer content JSONB field, fallback to mapping table result
        iso_clause = (
            content.get("iso_clause")
            or row["iso_clause"]
            or ""
        )

        # steps / evidence_fields come from the iso360_templates but are stored
        # in the content JSONB when documents are created; fall back gracefully.
        steps = content.get("steps") or []
        evidence_fields = content.get("evidence_fields") or []

        next_due_date: Optional[date] = row["next_due_date"]
        last_completed_at: Optional[datetime] = row["last_completed_at"]

        completion_status = _compute_completion_status(
            row["update_frequency"],
            next_due_date,
            last_completed_at,
            today,
        )

        activity = ISO360Activity(
            doc_id=str(row["doc_id"]),
            plan_id=pid,
            placeholder_key=row["placeholder_key"],
            title=row["title"],
            type=row["type"],
            update_frequency=row["update_frequency"],
            responsible_role=row["responsible_role"],
            iso_clause=iso_clause,
            status=row["status"],
            next_due_date=next_due_date.isoformat() if next_due_date else None,
            last_completed_at=(
                last_completed_at.isoformat() if last_completed_at else None
            ),
            steps=steps,
            evidence_fields=evidence_fields,
            completion_status=completion_status,
            excluded=bool(row["excluded"]),
        )
        plan_map[pid]["activities"].append(activity)

    # ── 5. Compute stats per plan ─────────────────────────────────────────────
    result_plans: List[ISO360Plan] = []
    for pid, pd in plan_map.items():
        activities: List[ISO360Activity] = pd["activities"]

        total = len(activities)
        due_soon = sum(1 for a in activities if a.completion_status == "due_soon")
        overdue = sum(1 for a in activities if a.completion_status == "overdue")
        event_based = sum(1 for a in activities if a.completion_status == "event_based")

        completed_this_year = 0
        for a in activities:
            if a.last_completed_at:
                try:
                    lc = datetime.fromisoformat(a.last_completed_at)
                    if lc.year == current_year:
                        completed_this_year += 1
                except ValueError:
                    pass

        stats = ISO360PlanStats(
            total=total,
            completed_this_year=completed_this_year,
            due_soon=due_soon,
            overdue=overdue,
            event_based=event_based,
        )

        result_plans.append(
            ISO360Plan(
                plan_id=pd["plan_id"],
                iso_code=pd["iso_code"],
                iso_name=pd["iso_name"],
                iso360_enabled=pd["iso360_enabled"],
                adjustment_pass_done=pd["adjustment_pass_done"],
                onboarding_threshold_pct=pd["onboarding_threshold_pct"],
                activities=activities,
                stats=stats,
            )
        )

    return ISO360CustomerResponse(plans=result_plans)


# ── Single activity fetch ─────────────────────────────────────────────────────

@router.get("/{customer_id}/iso360/activities/{doc_id}", response_model=ISO360Activity)
async def get_iso360_activity(
    customer_id: int,
    doc_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """Return a single ISO360 activity document with steps, evidence fields, and completion status."""
    pool = await get_db_pool()
    today = date.today()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                cd.id                  AS doc_id,
                cd.plan_id,
                cd.document_name       AS title,
                cd.status,
                cd.next_due_date,
                cd.last_completed_at,
                cd.content,
                COALESCE(cd.excluded, FALSE) AS excluded,
                t.placeholder_key,
                t.type,
                t.update_frequency,
                t.responsible_role,
                COALESCE(
                    (SELECT (tim.covered_clauses)[1]
                     FROM {_SCHEMA}.iso360_template_iso_mapping tim
                     WHERE tim.template_id = t.id LIMIT 1),
                    ''
                ) AS iso_clause
            FROM {_SCHEMA}.customer_documents   cd
            JOIN {_SCHEMA}.iso360_templates      t  ON t.id = cd.iso360_template_id
            WHERE cd.id = $1 AND cd.customer_id = $2
              AND cd.document_type = 'iso360_activity'
            """,
            doc_id, customer_id,
        )
    if not row:
        raise HTTPException(404, "ISO360 activity not found")

    content = _parse_jsonb(row["content"]) or {}
    iso_clause = content.get("iso_clause") or row["iso_clause"] or ""
    steps = content.get("steps") or []
    evidence_fields = content.get("evidence_fields") or []
    next_due_date: Optional[date] = row["next_due_date"]
    last_completed_at: Optional[datetime] = row["last_completed_at"]
    completion_status = _compute_completion_status(
        row["update_frequency"], next_due_date, last_completed_at, today
    )
    return ISO360Activity(
        doc_id=str(row["doc_id"]),
        plan_id=str(row["plan_id"]),
        placeholder_key=row["placeholder_key"],
        title=row["title"],
        type=row["type"],
        update_frequency=row["update_frequency"],
        responsible_role=row["responsible_role"],
        iso_clause=iso_clause,
        status=row["status"],
        next_due_date=next_due_date.isoformat() if next_due_date else None,
        last_completed_at=last_completed_at.isoformat() if last_completed_at else None,
        steps=steps,
        evidence_fields=evidence_fields,
        completion_status=completion_status,
        excluded=bool(row["excluded"]),
    )


# ── Trigger event-based activity ──────────────────────────────────────────────

class TriggerActivityResponse(BaseModel):
    task_id: str
    title: str
    message: str


@router.post("/{customer_id}/iso360/activities/{doc_id}/trigger", response_model=TriggerActivityResponse)
async def trigger_iso360_activity(
    customer_id: int,
    doc_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """
    Manually trigger an event-based ISO360 activity — creates a customer_task
    from the customer_document so it appears in the customer's tasks tab.
    Idempotent: skips if an open task already exists for this document.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Fetch the document
        doc = await conn.fetchrow(
            f"""SELECT cd.id, cd.customer_id, cd.plan_id, cd.document_name,
                       cd.content, cd.iso360_template_id, cd.document_type,
                       t.update_frequency, t.placeholder_key, t.responsible_role,
                       s.code as iso_code
                FROM {_SCHEMA}.customer_documents cd
                JOIN {_SCHEMA}.iso360_templates t ON t.id = cd.iso360_template_id
                JOIN {_SCHEMA}.customer_iso_plans p ON p.id = cd.plan_id
                JOIN {_SCHEMA}.iso_standards s ON s.id = p.iso_standard_id
                WHERE cd.id = $1 AND cd.customer_id = $2
                  AND cd.document_type = 'iso360_activity'""",
            doc_id, customer_id,
        )
        if not doc:
            raise HTTPException(404, "ISO360 activity not found for this customer")

        # Check for existing open task
        existing = await conn.fetchrow(
            f"""SELECT id FROM {_SCHEMA}.customer_tasks
                WHERE document_id = $1
                  AND status NOT IN ('completed', 'cancelled', 'answered')""",
            doc_id,
        )
        if existing:
            raise HTTPException(409, f"An open task already exists for this activity (id={existing['id']})")

        content = json.loads(doc["content"]) if isinstance(doc["content"], str) else (doc["content"] or {})
        title = doc["document_name"] or content.get("title") or doc["placeholder_key"]

        # Build evidence description from evidence_fields
        ev_fields = content.get("evidence_fields", [])
        required_fields = [f["field_name"] for f in ev_fields if f.get("required")]
        evidence_desc = f"Required: {', '.join(required_fields)}" if required_fields else "See activity steps"

        task_id = await conn.fetchval(
            f"""INSERT INTO {_SCHEMA}.customer_tasks
                    (customer_id, plan_id, document_id, task_type, task_scope,
                     title, description, status, priority,
                     requires_evidence, evidence_description,
                     auto_generated, source, placeholder_key, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, 'iso360_activity', 'plan',
                        $4, $5, 'pending', 'high',
                        $6, $7,
                        TRUE, 'iso360_manual_trigger', $8, $9, NOW(), NOW())
                RETURNING id""",
            customer_id,
            doc["plan_id"],
            doc_id,
            title,
            f"ISO360 {doc['iso_code']} — {content.get('responsible_role', 'Compliance Manager')}",
            len(ev_fields) > 0,
            evidence_desc,
            doc["placeholder_key"],
            current_user.get("user_id"),
        )

    logger.info(
        f"ISO360 activity triggered: doc={doc_id}, customer={customer_id}, "
        f"task={task_id}, by={current_user.get('user_id')}"
    )
    return TriggerActivityResponse(
        task_id=str(task_id),
        title=title,
        message="Task created and will appear in the customer's tasks tab.",
    )


# ── Exclude / un-exclude activity ─────────────────────────────────────────────

class ExcludeActivityResponse(BaseModel):
    doc_id: str
    excluded: bool


@router.patch("/{customer_id}/iso360/activities/{doc_id}/exclude", response_model=ExcludeActivityResponse)
async def set_iso360_activity_excluded(
    customer_id: int,
    doc_id: UUID,
    excluded: bool,
    current_user: dict = Depends(get_current_user),
):
    """Toggle the excluded flag on an ISO360 activity document.
    Excluded activities are visually dimmed and skipped by the scheduler.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""UPDATE {_SCHEMA}.customer_documents
                SET excluded = $1, updated_at = NOW()
                WHERE id = $2 AND customer_id = $3
                  AND document_type = 'iso360_activity'
                RETURNING id""",
            excluded, doc_id, customer_id,
        )
    if not row:
        raise HTTPException(404, "ISO360 activity not found for this customer")
    logger.info(
        f"ISO360 activity {'excluded' if excluded else 'included'}: "
        f"doc={doc_id}, customer={customer_id}, by={current_user.get('user_id')}"
    )
    return ExcludeActivityResponse(doc_id=str(doc_id), excluded=excluded)


# ── KYC Questionnaire ─────────────────────────────────────────────────────────

class KYCBatchStatus(BaseModel):
    batch_id: Optional[str] = None
    status: Optional[str] = None          # generating | pending | completed | adjustment_triggered | failed
    total_questions: int = 0
    answered_count: int = 0
    has_active_batch: bool = False
    error_message: Optional[str] = None


class KYCTriggerResponse(BaseModel):
    batch_id: str
    status: str
    message: str


@router.get("/{customer_id}/iso360/kyc/status", response_model=KYCBatchStatus)
async def get_kyc_status(
    customer_id: int,
    plan_id: Optional[UUID] = None,
    current_user: dict = Depends(get_current_user),
):
    """Return the most recent KYC batch status for a customer (optionally filtered by plan)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = f"""
            SELECT b.id, b.status, b.total_questions, b.answered_count, b.error_message,
                   COUNT(ct.id) FILTER (WHERE ct.status IN ('answered','completed')) AS answered_live
            FROM {_SCHEMA}.iso360_kyc_batches b
            LEFT JOIN {_SCHEMA}.customer_tasks ct ON ct.kyc_batch_id = b.id
                AND ct.task_type = 'kyc_question'
                AND (ct.is_ignored = FALSE OR ct.is_ignored IS NULL)
            WHERE b.customer_id = $1
        """
        params: list = [customer_id]
        if plan_id:
            query += " AND b.plan_id = $2"
            params.append(plan_id)
        query += " GROUP BY b.id ORDER BY b.created_at DESC LIMIT 1"

        row = await conn.fetchrow(query, *params)

    if not row:
        return KYCBatchStatus(has_active_batch=False)

    answered = row["answered_live"] or row["answered_count"] or 0
    return KYCBatchStatus(
        batch_id=str(row["id"]),
        status=row["status"],
        total_questions=row["total_questions"] or 0,
        answered_count=answered,
        has_active_batch=row["status"] not in ("failed",),
        error_message=row["error_message"],
    )


@router.post("/{customer_id}/iso360/kyc/trigger", response_model=KYCTriggerResponse)
async def trigger_kyc_batch(
    customer_id: int,
    plan_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """Create a KYC batch and push a job to the ai:iso360_kyc Redis stream.
    Returns 409 if there is already an active (non-failed, non-completed) batch.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Guard: block if active batch already exists
        active = await conn.fetchval(
            f"""SELECT id FROM {_SCHEMA}.iso360_kyc_batches
                WHERE customer_id = $1 AND plan_id = $2
                  AND status NOT IN ('completed','adjustment_triggered','failed')
                LIMIT 1""",
            customer_id, plan_id,
        )
        if active:
            raise HTTPException(409, f"KYC batch already active: {active}")

        # Fetch customer + plan info needed by the AI job
        plan_row = await conn.fetchrow(
            f"""SELECT p.id, p.iso_standard_id,
                       iso.code AS iso_code, iso.name AS iso_name,
                       c.name AS customer_name,
                       COALESCE(c.description, '') AS industry,
                       '' AS company_size
                FROM {_SCHEMA}.customer_iso_plans p
                JOIN {_SCHEMA}.iso_standards iso ON iso.id = p.iso_standard_id
                JOIN {_SCHEMA}.customers c ON c.id = p.customer_id
                WHERE p.id = $1 AND p.customer_id = $2 AND p.iso360_enabled = TRUE""",
            plan_id, customer_id,
        )
        if not plan_row:
            raise HTTPException(404, "ISO360 plan not found or ISO360 not enabled")

        # Create the batch record
        batch_id = await conn.fetchval(
            f"""INSERT INTO {_SCHEMA}.iso360_kyc_batches
                    (customer_id, plan_id, status)
                VALUES ($1, $2, 'generating')
                RETURNING id""",
            customer_id, plan_id,
        )

    # Push to AI service stream
    from ..redis_client import redis_client as _redis
    await _redis.add_to_stream("ai:iso360_kyc", {
        "batch_id":        str(batch_id),
        "customer_id":     str(customer_id),
        "plan_id":         str(plan_id),
        "iso_standard_id": str(plan_row["iso_standard_id"]),
        "iso_code":        plan_row["iso_code"],
        "iso_name":        plan_row["iso_name"],
        "customer_name":   plan_row["customer_name"],
        "industry":        plan_row["industry"],
        "company_size":    plan_row["company_size"],
    })

    logger.info(
        f"KYC batch triggered: batch={batch_id}, customer={customer_id}, "
        f"plan={plan_id}, by={current_user.get('user_id')}"
    )
    return KYCTriggerResponse(
        batch_id=str(batch_id),
        status="generating",
        message="KYC questionnaire is being generated by AI",
    )


@router.post("/{customer_id}/iso360/kyc/{batch_id}/check-completion")
async def check_kyc_completion(
    customer_id: int,
    batch_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """Check if all KYC questions are answered; if so, mark batch completed and trigger adjustment.
    Called by the frontend after each answer, or can be polled.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        batch = await conn.fetchrow(
            f"""SELECT id, plan_id, status, total_questions
                FROM {_SCHEMA}.iso360_kyc_batches
                WHERE id = $1 AND customer_id = $2""",
            batch_id, customer_id,
        )
        if not batch:
            raise HTTPException(404, "KYC batch not found")
        if batch["status"] in ("completed", "adjustment_triggered"):
            return {"status": batch["status"], "just_completed": False}

        answered = await conn.fetchval(
            f"""SELECT COUNT(*) FROM {_SCHEMA}.customer_tasks
                WHERE kyc_batch_id = $1
                  AND task_type = 'kyc_question'
                  AND status IN ('answered','completed')
                  AND (is_ignored = FALSE OR is_ignored IS NULL)""",
            batch_id,
        )
        total = batch["total_questions"] or 0

        if total > 0 and answered >= total:
            # Mark completed
            await conn.execute(
                f"""UPDATE {_SCHEMA}.iso360_kyc_batches
                    SET status = 'completed', answered_count = $1, completed_at = NOW()
                    WHERE id = $2""",
                answered, batch_id,
            )
            # Push adjustment job to AI service
            from ..redis_client import redis_client as _redis
            plan_id = str(batch["plan_id"])
            plan_row = await conn.fetchrow(
                f"""SELECT p.iso_standard_id, iso.code,
                           ps.reminder_month, ps.reminder_day
                    FROM {_SCHEMA}.customer_iso_plans p
                    JOIN {_SCHEMA}.iso_standards iso ON iso.id = p.iso_standard_id
                    LEFT JOIN {_SCHEMA}.iso360_plan_settings ps ON ps.plan_id = p.id
                    WHERE p.id = $1""",
                batch["plan_id"],
            )
            import uuid as _uuid
            job_id = str(_uuid.uuid4())
            await _redis.add_to_stream("ai:iso360_adjustment", {
                "job_id":           job_id,
                "plan_id":          plan_id,
                "customer_id":      str(customer_id),
                "iso_standard_id":  str(plan_row["iso_standard_id"]) if plan_row else "",
                "iso_standard":     plan_row["code"] if plan_row else "",
                "reminder_month":   str(plan_row["reminder_month"] or "") if plan_row else "",
                "reminder_day":     str(plan_row["reminder_day"] or "") if plan_row else "",
                "kyc_batch_id":     str(batch_id),
            })
            await conn.execute(
                f"""UPDATE {_SCHEMA}.iso360_kyc_batches
                    SET status = 'adjustment_triggered' WHERE id = $1""",
                batch_id,
            )
            logger.info(f"KYC batch {batch_id} complete — adjustment job {job_id} queued")
            return {"status": "adjustment_triggered", "just_completed": True}

        return {
            "status": batch["status"],
            "answered": answered,
            "total": total,
            "just_completed": False,
        }
