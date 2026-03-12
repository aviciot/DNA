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

from fastapi import APIRouter, Depends, HTTPException
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
