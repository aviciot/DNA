"""
ISO360 Health Dashboard API
===========================
GET /api/v1/iso360/health
Returns per-customer, per-plan ISO360 health stats for the admin dashboard.
"""
import logging
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import get_current_user
from ..config import settings
from ..database import get_db_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/iso360", tags=["iso360-health"])

_SCHEMA = settings.DATABASE_APP_SCHEMA


class ISO360PlanHealth(BaseModel):
    plan_id: str
    customer_id: int
    customer_name: str
    iso_code: str
    iso_name: str
    adjustment_pass_done: bool
    total: int               # all non-event-based, non-excluded activities
    on_track: int            # upcoming + completed
    overdue: int
    due_soon: int            # due within 30 days
    completed_this_year: int
    event_based: int         # total event-based activities
    last_activity_at: Optional[str]   # most recent last_completed_at across all activities


class ISO360HealthResponse(BaseModel):
    plans: List[ISO360PlanHealth]
    as_of: str


@router.get("/health", response_model=ISO360HealthResponse)
async def get_iso360_health(
    user: dict = Depends(get_current_user),
):
    """
    Returns health stats for every ISO360-enabled plan across all customers.
    Overdue/due_soon computed from next_due_date vs today.
    completed_this_year = activities with last_completed_at in current calendar year.
    """
    today = date.today()
    current_year = today.year

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                p.id                                        AS plan_id,
                p.customer_id,
                c.name                                      AS customer_name,
                iso.code                                    AS iso_code,
                iso.name                                    AS iso_name,
                COALESCE(ps.adjustment_pass_done, FALSE)    AS adjustment_pass_done,

                -- total non-event-based, non-excluded activities
                COUNT(*) FILTER (
                    WHERE t.update_frequency != 'event_based'
                      AND COALESCE(cd.excluded, FALSE) = FALSE
                ) AS total,

                -- overdue: next_due_date < today AND not completed this cycle
                COUNT(*) FILTER (
                    WHERE t.update_frequency != 'event_based'
                      AND COALESCE(cd.excluded, FALSE) = FALSE
                      AND cd.next_due_date IS NOT NULL
                      AND cd.next_due_date < $1
                      AND (cd.last_completed_at IS NULL
                           OR cd.last_completed_at::date < cd.next_due_date)
                ) AS overdue,

                -- due_soon: next_due_date between today and today+30
                COUNT(*) FILTER (
                    WHERE t.update_frequency != 'event_based'
                      AND COALESCE(cd.excluded, FALSE) = FALSE
                      AND cd.next_due_date IS NOT NULL
                      AND cd.next_due_date >= $1
                      AND cd.next_due_date <= $1 + INTERVAL '30 days'
                      AND (cd.last_completed_at IS NULL
                           OR cd.last_completed_at::date < cd.next_due_date)
                ) AS due_soon,

                -- completed this year
                COUNT(*) FILTER (
                    WHERE cd.last_completed_at IS NOT NULL
                      AND EXTRACT(YEAR FROM cd.last_completed_at) = $2
                ) AS completed_this_year,

                -- event-based count
                COUNT(*) FILTER (
                    WHERE t.update_frequency = 'event_based'
                      AND COALESCE(cd.excluded, FALSE) = FALSE
                ) AS event_based,

                -- last activity
                MAX(cd.last_completed_at)                   AS last_activity_at

            FROM {_SCHEMA}.customer_iso_plans          p
            JOIN {_SCHEMA}.iso_standards               iso ON iso.id = p.iso_standard_id
            JOIN {_SCHEMA}.customers                   c   ON c.id  = p.customer_id
            LEFT JOIN {_SCHEMA}.iso360_plan_settings   ps  ON ps.plan_id = p.id
            LEFT JOIN {_SCHEMA}.customer_documents     cd  ON cd.plan_id = p.id
                                                           AND cd.document_type = 'iso360_activity'
            LEFT JOIN {_SCHEMA}.iso360_templates       t   ON t.id = cd.iso360_template_id
            WHERE p.iso360_enabled = TRUE
            GROUP BY p.id, p.customer_id, c.name, iso.code, iso.name, ps.adjustment_pass_done
            ORDER BY c.name, iso.code
            """,
            today, current_year,
        )

    plans = []
    for row in rows:
        total    = row["total"]    or 0
        overdue  = row["overdue"]  or 0
        due_soon = row["due_soon"] or 0
        on_track = max(0, total - overdue)
        last_at  = row["last_activity_at"]
        plans.append(ISO360PlanHealth(
            plan_id=str(row["plan_id"]),
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            iso_code=row["iso_code"],
            iso_name=row["iso_name"],
            adjustment_pass_done=bool(row["adjustment_pass_done"]),
            total=total,
            on_track=on_track,
            overdue=overdue,
            due_soon=due_soon,
            completed_this_year=row["completed_this_year"] or 0,
            event_based=row["event_based"] or 0,
            last_activity_at=last_at.isoformat() if last_at else None,
        ))

    return ISO360HealthResponse(plans=plans, as_of=today.isoformat())
