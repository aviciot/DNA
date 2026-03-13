"""
Phase 3B: Task Management API
==============================
Manual and auto task management, task templates
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncpg

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Task Management"])


# =====================================================
# Pydantic Models
# =====================================================

class TaskCreate(BaseModel):
    """Create manual task."""
    customer_id: int
    plan_id: Optional[UUID] = None
    task_type: str = "custom"
    task_scope: str = "customer"  # 'customer', 'iso_plan', 'document'
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[date] = None
    assigned_to: Optional[int] = None
    manual_task_context: Optional[str] = None
    requires_evidence: bool = False
    evidence_description: Optional[str] = None


class TaskFromTemplateCreate(BaseModel):
    """Create task from template."""
    customer_id: int
    template_id: UUID
    plan_id: Optional[UUID] = None
    variables: Optional[dict] = {}  # For variable interpolation


class TaskUpdate(BaseModel):
    """Update task."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class TaskResponse(BaseModel):
    """Task response."""
    id: UUID
    customer_id: int
    customer_name: str
    plan_id: Optional[UUID]
    task_type: str
    task_scope: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    auto_generated: bool
    requires_evidence: bool
    evidence_description: Optional[str]
    due_date: Optional[date]
    assigned_to: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    is_ignored: bool = False
    ignore_reason: Optional[str] = None
    placeholder_key: Optional[str] = None
    answered_via: Optional[str] = None
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None
    collection_request_id: Optional[UUID] = None
    needs_human_review: bool = False
    human_review_reason: Optional[str] = None
    extraction_confidence: Optional[float] = None
    extraction_reasoning: Optional[str] = None
    reviewed_by_human: bool = False
    evidence_files: Optional[list] = None
    document_id: Optional[UUID] = None
    source: Optional[str] = None
    kyc_batch_id: Optional[UUID] = None


class TaskTemplateResponse(BaseModel):
    """Task template response."""
    id: UUID
    template_name: str
    template_description: Optional[str]
    task_type: str
    task_scope: str
    default_title: Optional[str]
    default_description: Optional[str]
    default_priority: str
    default_due_in_days: Optional[int]
    usage_count: int
    is_system_template: bool


# =====================================================
# Task Endpoints
# =====================================================

@router.post("/tasks", response_model=TaskResponse)
async def create_manual_task(
    task: TaskCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a manual task (not auto-generated from templates).
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Verify customer exists
            customer_row = await conn.fetchrow(
                "SELECT id, name FROM dna_app.customers WHERE id = $1",
                task.customer_id
            )
            if not customer_row:
                raise HTTPException(404, "Customer not found")

            # Create task
            row = await conn.fetchrow("""
                INSERT INTO dna_app.customer_tasks (
                    customer_id, plan_id, task_type, task_scope,
                    title, description, priority, due_date,
                    assigned_to, auto_generated, created_manually_by,
                    manual_task_context, requires_evidence, evidence_description, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id, customer_id, plan_id, task_type, task_scope,
                          title, description, status, priority, auto_generated,
                          requires_evidence, evidence_description, due_date,
                          assigned_to, created_at, completed_at, is_ignored,
                          ignore_reason
            """,
                task.customer_id, task.plan_id, task.task_type, task.task_scope,
                task.title, task.description, task.priority, task.due_date,
                task.assigned_to, False, user.get("user_id"),
                task.manual_task_context, task.requires_evidence,
                task.evidence_description, 'pending'
            )

            logger.info(f"Manual task created: {row['id']} by user {user.get('user_id')}")

            return TaskResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                customer_name=customer_row['name'],
                plan_id=row['plan_id'],
                task_type=row['task_type'],
                task_scope=row['task_scope'],
                title=row['title'],
                description=row['description'],
                status=row['status'],
                priority=row['priority'],
                auto_generated=row['auto_generated'],
                requires_evidence=row['requires_evidence'],
                evidence_description=row['evidence_description'],
                due_date=row['due_date'],
                assigned_to=row['assigned_to'],
                created_at=row['created_at'],
                completed_at=row['completed_at'],
                is_ignored=row['is_ignored'] or False,
                ignore_reason=row['ignore_reason']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(500, f"Failed to create task: {str(e)}")


@router.post("/tasks/from-template", response_model=TaskResponse)
async def create_task_from_template(
    request: TaskFromTemplateCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a manual task from a task template.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get template
                template_row = await conn.fetchrow("""
                    SELECT template_name, task_type, task_scope, default_title,
                           default_description, default_priority, default_due_in_days
                    FROM dna_app.task_templates
                    WHERE id = $1 AND is_active = true
                """, request.template_id)

                if not template_row:
                    raise HTTPException(404, "Task template not found")

                # Get customer
                customer_row = await conn.fetchrow(
                    "SELECT id, name FROM dna_app.customers WHERE id = $1",
                    request.customer_id
                )
                if not customer_row:
                    raise HTTPException(404, "Customer not found")

                # Interpolate variables in title and description
                title = template_row['default_title'] or ""
                description = template_row['default_description'] or ""

                for var_name, var_value in request.variables.items():
                    title = title.replace(f"{{{{{var_name}}}}}", str(var_value))
                    description = description.replace(f"{{{{{var_name}}}}}", str(var_value))

                # Calculate due date
                due_date = None
                if template_row['default_due_in_days']:
                    from datetime import date, timedelta
                    due_date = date.today() + timedelta(days=template_row['default_due_in_days'])

                # Create task
                task_row = await conn.fetchrow("""
                    INSERT INTO dna_app.customer_tasks (
                        customer_id, plan_id, task_type, task_scope,
                        title, description, priority, due_date,
                        auto_generated, created_manually_by, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING id, customer_id, plan_id, task_type, task_scope,
                              title, description, status, priority, auto_generated,
                              requires_evidence, evidence_description, due_date,
                              assigned_to, created_at, completed_at, is_ignored,
                              ignore_reason
                """,
                    request.customer_id, request.plan_id, template_row['task_type'],
                    template_row['task_scope'], title, description,
                    template_row['default_priority'], due_date, False,
                    user.get("user_id"), 'pending'
                )

                # Update template usage
                await conn.execute("""
                    UPDATE dna_app.task_templates
                    SET usage_count = usage_count + 1, last_used_at = NOW()
                    WHERE id = $1
                """, request.template_id)

                logger.info(f"Task created from template {request.template_id}: {task_row['id']}")

                return TaskResponse(
                    id=task_row['id'],
                    customer_id=task_row['customer_id'],
                    customer_name=customer_row['name'],
                    plan_id=task_row['plan_id'],
                    task_type=task_row['task_type'],
                    task_scope=task_row['task_scope'],
                    title=task_row['title'],
                    description=task_row['description'],
                    status=task_row['status'],
                    priority=task_row['priority'],
                    auto_generated=task_row['auto_generated'],
                    requires_evidence=task_row['requires_evidence'],
                    evidence_description=task_row['evidence_description'],
                    due_date=task_row['due_date'],
                    assigned_to=task_row['assigned_to'],
                    created_at=task_row['created_at'],
                    completed_at=task_row['completed_at'],
                    is_ignored=task_row['is_ignored'] or False,
                    ignore_reason=task_row['ignore_reason']
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task from template: {e}")
        raise HTTPException(500, f"Failed to create task: {str(e)}")


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    customer_id: Optional[int] = Query(None),
    plan_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    include_ignored: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=1000),
    user: dict = Depends(get_current_user)
):
    """
    List tasks with filters.
    """
    pool = await get_db_pool()
    offset = (page - 1) * page_size

    try:
        async with pool.acquire() as conn:
            # Build query
            where_clauses = []
            params = []
            param_idx = 1

            if customer_id:
                where_clauses.append(f"ct.customer_id = ${param_idx}")
                params.append(customer_id)
                param_idx += 1

            if plan_id:
                where_clauses.append(f"ct.plan_id = ${param_idx}")
                params.append(plan_id)
                param_idx += 1

            if status:
                where_clauses.append(f"ct.status = ${param_idx}")
                params.append(status)
                param_idx += 1

            if priority:
                where_clauses.append(f"ct.priority = ${param_idx}")
                params.append(priority)
                param_idx += 1

            if assigned_to:
                where_clauses.append(f"ct.assigned_to = ${param_idx}")
                params.append(assigned_to)
                param_idx += 1

            if not include_ignored:
                where_clauses.append("(ct.is_ignored = false OR ct.is_ignored IS NULL)")

            # Always exclude internal task types from the regular task list
            where_clauses.append("ct.task_type NOT IN ('notification', 'kyc_question')")

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            params.extend([page_size, offset])

            rows = await conn.fetch(f"""
                SELECT
                    ct.id, ct.customer_id, c.name as customer_name, ct.plan_id,
                    ct.task_type, ct.task_scope, ct.title, ct.description,
                    ct.status, ct.priority, ct.auto_generated, ct.requires_evidence,
                    ct.evidence_description, ct.due_date, ct.assigned_to,
                    ct.created_at, ct.completed_at, ct.updated_at, ct.is_ignored, ct.ignore_reason,
                    ct.placeholder_key, ct.answered_via, ct.answer, ct.answered_at,
                    ct.notes, ct.collection_request_id,
                    COALESCE(ct.needs_human_review, FALSE) AS needs_human_review,
                    ct.human_review_reason,
                    ct.extraction_confidence, ct.extraction_reasoning,
                    COALESCE(ct.reviewed_by_human, FALSE) AS reviewed_by_human,
                    ct.evidence_files,
                    ct.document_id,
                    ct.source,
                    ct.kyc_batch_id
                FROM dna_app.customer_tasks ct
                JOIN dna_app.customers c ON ct.customer_id = c.id
                {where_sql}
                ORDER BY
                    CASE ct.priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        ELSE 4
                    END,
                    ct.due_date ASC NULLS LAST,
                    ct.created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """, *params)

            return [
                TaskResponse(
                    id=row['id'],
                    customer_id=row['customer_id'],
                    customer_name=row['customer_name'],
                    plan_id=row['plan_id'],
                    task_type=row['task_type'],
                    task_scope=row['task_scope'],
                    title=row['title'],
                    description=row['description'],
                    status=row['status'],
                    priority=row['priority'],
                    auto_generated=row['auto_generated'],
                    requires_evidence=row['requires_evidence'],
                    evidence_description=row['evidence_description'],
                    due_date=row['due_date'],
                    assigned_to=row['assigned_to'],
                    created_at=row['created_at'],
                    completed_at=row['completed_at'],
                    is_ignored=row['is_ignored'] or False,
                    ignore_reason=row['ignore_reason'],
                    placeholder_key=row['placeholder_key'],
                    answered_via=row['answered_via'],
                    answer=row['answer'],
                    answered_at=row['answered_at'],
                    updated_at=row['updated_at'],
                    notes=row['notes'],
                    collection_request_id=row['collection_request_id'],
                    needs_human_review=row['needs_human_review'] or False,
                    human_review_reason=row['human_review_reason'],
                    extraction_confidence=row['extraction_confidence'],
                    extraction_reasoning=row['extraction_reasoning'],
                    reviewed_by_human=row['reviewed_by_human'] or False,
                    evidence_files=json.loads(row['evidence_files']) if isinstance(row['evidence_files'], str) else (row['evidence_files'] or None),
                    document_id=row['document_id'],
                    source=row['source'],
                    kyc_batch_id=row['kyc_batch_id'],
                )
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(500, f"Failed to list tasks: {str(e)}")


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    updates: TaskUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update task details.
    """
    pool = await get_db_pool()

    # Build update query
    update_fields = []
    params = []
    param_idx = 1

    for field, value in updates.dict(exclude_unset=True).items():
        if value is not None:
            update_fields.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not update_fields:
        raise HTTPException(400, "No fields to update")

    params.append(task_id)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                UPDATE dna_app.customer_tasks ct
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE ct.id = ${param_idx}
                RETURNING ct.id, ct.customer_id, ct.plan_id, ct.task_type, ct.task_scope,
                          ct.title, ct.description, ct.status, ct.priority, ct.auto_generated,
                          ct.requires_evidence, ct.evidence_description, ct.due_date,
                          ct.assigned_to, ct.created_at, ct.completed_at, ct.is_ignored,
                          ct.ignore_reason
            """, *params)

            if not row:
                raise HTTPException(404, "Task not found")

            # Get customer name
            customer_row = await conn.fetchrow(
                "SELECT name FROM dna_app.customers WHERE id = $1",
                row['customer_id']
            )

            logger.info(f"Task updated: {task_id} by user {user.get('user_id')}")

            return TaskResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                customer_name=customer_row['name'],
                plan_id=row['plan_id'],
                task_type=row['task_type'],
                task_scope=row['task_scope'],
                title=row['title'],
                description=row['description'],
                status=row['status'],
                priority=row['priority'],
                auto_generated=row['auto_generated'],
                requires_evidence=row['requires_evidence'],
                evidence_description=row['evidence_description'],
                due_date=row['due_date'],
                assigned_to=row['assigned_to'],
                created_at=row['created_at'],
                completed_at=row['completed_at'],
                is_ignored=row['is_ignored'] or False,
                ignore_reason=row['ignore_reason']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(500, f"Failed to update task: {str(e)}")


@router.post("/tasks/{task_id}/ignore")
async def ignore_task(
    task_id: UUID,
    reason: Optional[str] = Query(None, description="Reason for ignoring"),
    user: dict = Depends(get_current_user)
):
    """
    Mark task as ignored (not deleted, kept for audit trail).
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                UPDATE dna_app.customer_tasks
                SET is_ignored = true, ignored_at = NOW(),
                    ignored_by = $2, ignore_reason = $3
                WHERE id = $1
                RETURNING id
            """, task_id, user.get("user_id"), reason or "Marked as ignored")

            if not result:
                raise HTTPException(404, "Task not found")

            logger.info(f"Task ignored: {task_id} by user {user.get('user_id')}")

            return {
                "message": "Task marked as ignored successfully",
                "task_id": str(task_id)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ignoring task: {e}")
        raise HTTPException(500, f"Failed to ignore task: {str(e)}")


# =====================================================
# Task Template Endpoints
# =====================================================

@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Mark a task as completed. For ISO360 activities, advances next_due_date on the source document."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE dna_app.customer_tasks
                SET status = 'completed', completed_at = NOW(), updated_at = NOW(),
                    reviewed_by_human = TRUE
                WHERE id = $1
                RETURNING id, customer_id, plan_id, task_type, task_scope,
                          title, description, status, priority, auto_generated,
                          requires_evidence, evidence_description, due_date,
                          assigned_to, created_at, completed_at, is_ignored, ignore_reason,
                          extraction_confidence, extraction_reasoning,
                          reviewed_by_human, evidence_files, document_id
            """, task_id)
            if not row:
                raise HTTPException(404, "Task not found")

            # For ISO360 activities: mark last_completed_at and advance next_due_date
            if row["task_type"] == "iso360_activity" and row["document_id"]:
                await conn.execute(
                    """UPDATE dna_app.customer_documents cd
                       SET last_completed_at = NOW(),
                           next_due_date = CASE
                               WHEN t.update_frequency = 'monthly'   THEN cd.next_due_date + INTERVAL '1 month'
                               WHEN t.update_frequency = 'quarterly' THEN cd.next_due_date + INTERVAL '3 months'
                               WHEN t.update_frequency = 'yearly'    THEN cd.next_due_date + INTERVAL '1 year'
                               ELSE cd.next_due_date
                           END,
                           updated_at = NOW()
                       FROM dna_app.iso360_templates t
                       WHERE cd.id = $1
                         AND t.id = cd.iso360_template_id""",
                    row["document_id"],
                )
                logger.info(f"ISO360 activity completed: advanced next_due_date for doc {row['document_id']}")

            customer = await conn.fetchrow("SELECT name FROM dna_app.customers WHERE id = $1", row["customer_id"])
            logger.info(f"Task completed: {task_id} by user {user.get('user_id')}")
            ev_files = row['evidence_files']
            return TaskResponse(
                customer_name=customer["name"],
                **{k: row[k] for k in TaskResponse.__fields__ if k not in ("customer_name", "evidence_files", "document_id") and k in row.keys()},
                evidence_files=json.loads(ev_files) if isinstance(ev_files, str) else (ev_files or None),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing task {task_id}: {e}")
        raise HTTPException(500, str(e))


class TaskReasonBody(BaseModel):
    reason: Optional[str] = None


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    body: TaskReasonBody = TaskReasonBody(),
    user: dict = Depends(get_current_user)
):
    """Cancel a task with an optional reason (stored in notes)."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE dna_app.customer_tasks
                SET status = 'cancelled', notes = $2, updated_at = NOW()
                WHERE id = $1
                RETURNING id, customer_id, plan_id, task_type, task_scope,
                          title, description, status, priority, auto_generated,
                          requires_evidence, evidence_description, due_date,
                          assigned_to, created_at, completed_at, is_ignored, ignore_reason
            """, task_id, body.reason or "Cancelled by user")
            if not row:
                raise HTTPException(404, "Task not found")
            customer = await conn.fetchrow("SELECT name FROM dna_app.customers WHERE id = $1", row["customer_id"])
            logger.info(f"Task cancelled: {task_id} reason='{body.reason}' by user {user.get('user_id')}")
            return TaskResponse(customer_name=customer["name"], **{k: row[k] for k in TaskResponse.__fields__ if k != "customer_name" and k in row.keys()})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(500, str(e))


@router.post("/tasks/{task_id}/hold")
async def hold_task(
    task_id: UUID,
    body: TaskReasonBody = TaskReasonBody(),
    user: dict = Depends(get_current_user)
):
    """Put a task on hold with an optional reason (stored in notes)."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE dna_app.customer_tasks
                SET status = 'on_hold', notes = $2, updated_at = NOW()
                WHERE id = $1
                RETURNING id, customer_id, plan_id, task_type, task_scope,
                          title, description, status, priority, auto_generated,
                          requires_evidence, evidence_description, due_date,
                          assigned_to, created_at, completed_at, is_ignored, ignore_reason
            """, task_id, body.reason or "On hold")
            if not row:
                raise HTTPException(404, "Task not found")
            customer = await conn.fetchrow("SELECT name FROM dna_app.customers WHERE id = $1", row["customer_id"])
            logger.info(f"Task on hold: {task_id} reason='{body.reason}' by user {user.get('user_id')}")
            return TaskResponse(customer_name=customer["name"], **{k: row[k] for k in TaskResponse.__fields__ if k != "customer_name" and k in row.keys()})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error putting task on hold {task_id}: {e}")
        raise HTTPException(500, str(e))


class ToggleHumanReviewBody(BaseModel):
    needs_human_review: bool
    reason: Optional[str] = None


@router.post("/tasks/{task_id}/toggle-human-review")
async def toggle_human_review(
    task_id: UUID,
    body: ToggleHumanReviewBody,
    user: dict = Depends(get_current_user),
):
    """Set or clear the needs_human_review flag on a task."""
    pool = await get_db_pool()
    schema = "dna_app"
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""UPDATE {schema}.customer_tasks
                    SET needs_human_review = $2,
                        human_review_reason = CASE WHEN $2 THEN $3 ELSE NULL END,
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING id, needs_human_review, human_review_reason""",
                task_id, body.needs_human_review, body.reason,
            )
            if not row:
                raise HTTPException(404, "Task not found")
        logger.info(f"toggle_human_review: task={task_id} set to {body.needs_human_review} by user {user.get('user_id')}")
        return {"ok": True, "needs_human_review": row["needs_human_review"], "human_review_reason": row["human_review_reason"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling human review on task {task_id}: {e}")
        raise HTTPException(500, str(e))


@router.get("/task-templates", response_model=List[TaskTemplateResponse])
async def list_task_templates(
    task_scope: Optional[str] = Query(None),
    is_system: Optional[bool] = Query(None),
    user: dict = Depends(get_current_user)
):
    """
    List available task templates.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            where_clauses = ["is_active = true"]
            params = []
            param_idx = 1

            if task_scope:
                where_clauses.append(f"task_scope = ${param_idx}")
                params.append(task_scope)
                param_idx += 1

            if is_system is not None:
                where_clauses.append(f"is_system_template = ${param_idx}")
                params.append(is_system)
                param_idx += 1

            where_sql = "WHERE " + " AND ".join(where_clauses)

            rows = await conn.fetch(f"""
                SELECT
                    id, template_name, template_description, task_type,
                    task_scope, default_title, default_description,
                    default_priority, default_due_in_days, usage_count,
                    is_system_template
                FROM dna_app.task_templates
                {where_sql}
                ORDER BY task_scope, template_name
            """, *params)

            return [
                TaskTemplateResponse(
                    id=row['id'],
                    template_name=row['template_name'],
                    template_description=row['template_description'],
                    task_type=row['task_type'],
                    task_scope=row['task_scope'],
                    default_title=row['default_title'],
                    default_description=row['default_description'],
                    default_priority=row['default_priority'],
                    default_due_in_days=row['default_due_in_days'],
                    usage_count=row['usage_count'],
                    is_system_template=row['is_system_template']
                )
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Error listing task templates: {e}")
        raise HTTPException(500, f"Failed to list task templates: {str(e)}")


# =====================================================
# Evidence file serve
# =====================================================

@router.get("/tasks/{task_id}/evidence/{filename}")
async def serve_evidence_file(
    task_id: UUID,
    filename: str,
    user: dict = Depends(get_current_user),
):
    """Serve an evidence file attached to a task (for preview/download)."""
    # Sanitize filename — reject path traversal attempts
    safe_filename = re.sub(r'[^a-zA-Z0-9._\- ]', '_', filename)
    if safe_filename != filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT customer_id, evidence_files FROM dna_app.customer_tasks WHERE id = $1", task_id
        )
    if not row:
        raise HTTPException(404, "Task not found")

    customer_id = row["customer_id"]

    # Build candidate paths to try in order:
    # 1. Path stored in evidence_files JSONB (recorded by automation-service with /app/storage/customers/ prefix)
    #    → translate to backend prefix /app/storage/ since volumes differ
    # 2. Reconstructed path (auto-apply via automation-service)
    # 3. Reconstructed path (accept via backend)
    candidates: list[Path] = []

    raw_ev = row["evidence_files"]
    if raw_ev:
        ev_list = json.loads(raw_ev) if isinstance(raw_ev, str) else (raw_ev or [])
        entry = next((f for f in ev_list if isinstance(f, dict) and f.get("filename") == safe_filename), None)
        if entry and entry.get("path"):
            p = entry["path"]
            if p.startswith("/app/storage/customers/"):
                p = "/app/storage/" + p[len("/app/storage/customers/"):]
            candidates.append(Path(p))

    candidates.append(Path(f"/app/storage/{customer_id}/evidence/{task_id}/{safe_filename}"))
    candidates.append(Path(f"/app/storage/customers/{customer_id}/evidence/{task_id}/{safe_filename}"))

    for file_path in candidates:
        if file_path.exists():
            return FileResponse(str(file_path), filename=safe_filename)

    raise HTTPException(404, "Evidence file not found")
