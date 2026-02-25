"""
Phase 3B: Progress Tracking API
================================
Customer progress views and dashboard statistics
"""

import logging
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Progress Tracking"])


# =====================================================
# Pydantic Models
# =====================================================

class ISOProgressResponse(BaseModel):
    """ISO-level progress."""
    id: UUID
    customer_id: int
    customer_name: str
    iso_standard_id: UUID
    iso_code: str
    iso_name: str
    plan_name: Optional[str]
    plan_status: str
    target_completion_date: Optional[str]

    # Template progress
    total_templates: int
    completed_templates: int
    in_progress_templates: int

    # Task progress
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    ignored_tasks: int

    # Overall progress
    progress_percentage: int

    created_at: datetime
    updated_at: Optional[datetime]


class CustomerProgressResponse(BaseModel):
    """Overall customer progress."""
    customer_id: int
    customer_name: str
    iso_plans: List[ISOProgressResponse]

    # Summary
    total_iso_plans: int
    total_templates: int
    total_tasks: int
    completed_tasks: int
    overall_progress: int


class DashboardStatsResponse(BaseModel):
    """Admin dashboard statistics."""
    total_customers: int
    active_customers: int
    total_iso_plans: int
    total_templates_assigned: int
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int

    # Today's activity
    customers_created_today: int
    tasks_completed_today: int


# =====================================================
# Endpoints
# =====================================================

@router.get("/customers/{customer_id}/progress", response_model=CustomerProgressResponse)
async def get_customer_progress(
    customer_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Get comprehensive progress overview for a customer.

    Shows progress across all ISO standards and templates.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            customer_row = await conn.fetchrow("""
                SELECT id, name FROM dna_app.customers WHERE id = $1
            """, customer_id)

            if not customer_row:
                raise HTTPException(404, "Customer not found")

            iso_progress_rows = await conn.fetch("""
                SELECT
                    v.id, v.customer_id, v.iso_standard_id, v.iso_code, v.iso_name,
                    v.plan_name, v.plan_status, v.target_completion_date,
                    v.total_templates, v.completed_templates, v.in_progress_templates,
                    v.total_tasks, v.completed_tasks, v.in_progress_tasks,
                    v.pending_tasks, v.ignored_tasks, v.progress_percentage,
                    v.created_at, v.updated_at
                FROM dna_app.v_customer_iso_progress v
                WHERE v.customer_id = $1
                ORDER BY v.created_at DESC
            """, customer_id)

            iso_plans = [
                ISOProgressResponse(
                    id=row['id'],
                    customer_id=row['customer_id'],
                    customer_name=customer_row['name'],
                    iso_standard_id=row['iso_standard_id'],
                    iso_code=row['iso_code'],
                    iso_name=row['iso_name'],
                    plan_name=row['plan_name'],
                    plan_status=row['plan_status'],
                    target_completion_date=row['target_completion_date'].isoformat() if row['target_completion_date'] else None,
                    total_templates=row['total_templates'],
                    completed_templates=row['completed_templates'],
                    in_progress_templates=row['in_progress_templates'],
                    total_tasks=row['total_tasks'],
                    completed_tasks=row['completed_tasks'],
                    in_progress_tasks=row['in_progress_tasks'],
                    pending_tasks=row['pending_tasks'],
                    ignored_tasks=row['ignored_tasks'],
                    progress_percentage=row['progress_percentage'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in iso_progress_rows
            ]

            total_templates = sum(iso.total_templates for iso in iso_plans)
            total_tasks = sum(iso.total_tasks for iso in iso_plans)
            completed_tasks = sum(iso.completed_tasks for iso in iso_plans)
            overall_progress = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0

            return CustomerProgressResponse(
                customer_id=customer_id,
                customer_name=customer_row['name'],
                iso_plans=iso_plans,
                total_iso_plans=len(iso_plans),
                total_templates=total_templates,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                overall_progress=overall_progress
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer progress: {e}")
        raise HTTPException(500, f"Failed to get customer progress: {str(e)}")


@router.get("/customers/{customer_id}/progress/{iso_standard_id}", response_model=ISOProgressResponse)
async def get_iso_progress(
    customer_id: int,
    iso_standard_id: UUID,
    user: dict = Depends(get_current_user)
):
    """
    Get detailed progress for a specific ISO standard.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            customer_row = await conn.fetchrow(
                "SELECT name FROM dna_app.customers WHERE id = $1",
                customer_id
            )
            if not customer_row:
                raise HTTPException(404, "Customer not found")

            row = await conn.fetchrow("""
                SELECT
                    v.id, v.customer_id, v.iso_standard_id, v.iso_code, v.iso_name,
                    v.plan_name, v.plan_status, v.target_completion_date,
                    v.total_templates, v.completed_templates, v.in_progress_templates,
                    v.total_tasks, v.completed_tasks, v.in_progress_tasks,
                    v.pending_tasks, v.ignored_tasks, v.progress_percentage,
                    v.created_at, v.updated_at
                FROM dna_app.v_customer_iso_progress v
                WHERE v.customer_id = $1 AND v.iso_standard_id = $2
            """, customer_id, iso_standard_id)

            if not row:
                raise HTTPException(404, "ISO plan not found for this customer")

            return ISOProgressResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                customer_name=customer_row['name'],
                iso_standard_id=row['iso_standard_id'],
                iso_code=row['iso_code'],
                iso_name=row['iso_name'],
                plan_name=row['plan_name'],
                plan_status=row['plan_status'],
                target_completion_date=row['target_completion_date'].isoformat() if row['target_completion_date'] else None,
                total_templates=row['total_templates'],
                completed_templates=row['completed_templates'],
                in_progress_templates=row['in_progress_templates'],
                total_tasks=row['total_tasks'],
                completed_tasks=row['completed_tasks'],
                in_progress_tasks=row['in_progress_tasks'],
                pending_tasks=row['pending_tasks'],
                ignored_tasks=row['ignored_tasks'],
                progress_percentage=row['progress_percentage'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ISO progress: {e}")
        raise HTTPException(500, f"Failed to get ISO progress: {str(e)}")


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    user: dict = Depends(get_current_user)
):
    """
    Get comprehensive dashboard statistics for admin.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(DISTINCT c.id) as total_customers,
                    COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'active') as active_customers,
                    COUNT(DISTINCT cip.id) FILTER (WHERE cip.is_ignored = false OR cip.is_ignored IS NULL) as total_iso_plans,
                    COUNT(DISTINCT cipt.template_id) FILTER (WHERE cipt.is_ignored = false OR cipt.is_ignored IS NULL) as total_templates_assigned,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL) as total_tasks,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as completed_tasks,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'pending' AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as pending_tasks,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status IN ('pending', 'in_progress') AND ct.due_date < CURRENT_DATE AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as overdue_tasks,
                    COUNT(DISTINCT c.id) FILTER (WHERE c.created_at::date = CURRENT_DATE) as customers_created_today,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.completed_at::date = CURRENT_DATE) as tasks_completed_today
                FROM dna_app.customers c
                LEFT JOIN dna_app.customer_iso_plans cip ON c.id = cip.customer_id
                LEFT JOIN dna_app.customer_iso_plan_templates cipt ON cip.id = cipt.plan_id
                LEFT JOIN dna_app.customer_tasks ct ON c.id = ct.customer_id
            """)

            return DashboardStatsResponse(
                total_customers=stats['total_customers'],
                active_customers=stats['active_customers'],
                total_iso_plans=stats['total_iso_plans'],
                total_templates_assigned=stats['total_templates_assigned'],
                total_tasks=stats['total_tasks'],
                completed_tasks=stats['completed_tasks'],
                pending_tasks=stats['pending_tasks'],
                overdue_tasks=stats['overdue_tasks'],
                customers_created_today=stats['customers_created_today'],
                tasks_completed_today=stats['tasks_completed_today']
            )

    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(500, f"Failed to get dashboard stats: {str(e)}")
