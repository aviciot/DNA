"""
Phase 3B: Plan Management API
==============================
Assign ISOs and templates to customers, generate tasks
"""

import logging
import json
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import asyncpg

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Plan Management"])


# =====================================================
# Pydantic Models
# =====================================================

class PlanCreate(BaseModel):
    """Create ISO plan for customer."""
    customer_id: int
    iso_standard_id: UUID
    plan_name: Optional[str] = None
    target_completion_date: Optional[date] = None


class PlanResponse(BaseModel):
    """Plan response."""
    id: UUID
    customer_id: int
    iso_standard_id: UUID
    iso_code: str
    iso_name: str
    plan_name: Optional[str]
    plan_status: str
    target_completion_date: Optional[date]
    created_at: datetime

    # Progress
    total_templates: int = 0
    completed_templates: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    progress_percentage: int = 0


class TemplateAssignment(BaseModel):
    """Assign template to plan."""
    template_ids: List[UUID]


class TaskGenerationRequest(BaseModel):
    """Generate tasks from templates."""
    due_date_offset_days: int = 30  # Default due date offset


class TaskGenerationResponse(BaseModel):
    """Task generation result."""
    plan_id: UUID
    total_templates: int
    total_tasks_generated: int
    tasks_by_template: dict


class PlanCreateComplete(BaseModel):
    """Create complete plan with templates and tasks in one transaction."""
    customer_id: int
    iso_standard_id: UUID
    template_ids: List[UUID]
    plan_name: Optional[str] = None
    target_completion_date: Optional[date] = None
    due_date_offset_days: int = 30


class PlanCreateCompleteResponse(BaseModel):
    """Complete plan creation response."""
    plan_id: UUID
    customer_id: int
    iso_standard_id: UUID
    iso_code: str
    iso_name: str
    templates_added: int
    tasks_created: int
    message: str


# =====================================================
# Endpoints
# =====================================================

@router.post("/plans/complete", response_model=PlanCreateCompleteResponse)
async def create_plan_complete(
    request: PlanCreateComplete,
    user: dict = Depends(get_current_user)
):
    """
    Create complete plan with templates and tasks in ONE ATOMIC TRANSACTION.

    This endpoint combines:
    1. Create ISO plan
    2. Add templates to plan
    3. Generate tasks from templates

    If ANY step fails, everything rolls back - no partial data!
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Step 1: Validate customer exists
                customer_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM dna_app.customers WHERE id = $1)",
                    request.customer_id
                )
                if not customer_exists:
                    raise HTTPException(404, "Customer not found")

                # Step 2: Validate ISO exists
                iso_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM dna_app.iso_standards WHERE id = $1)",
                    request.iso_standard_id
                )
                if not iso_exists:
                    raise HTTPException(404, "ISO standard not found")

                # Step 3: Get ISO details
                iso_row = await conn.fetchrow(
                    "SELECT code, name FROM dna_app.iso_standards WHERE id = $1",
                    request.iso_standard_id
                )

                # Step 4: Create plan (or reactivate ignored one)
                # Use ON CONFLICT to update if an ignored plan exists
                plan_row = await conn.fetchrow("""
                    INSERT INTO dna_app.customer_iso_plans (
                        customer_id, iso_standard_id, plan_name,
                        target_completion_date, created_by, created_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (customer_id, iso_standard_id)
                    DO UPDATE SET
                        plan_name = EXCLUDED.plan_name,
                        target_completion_date = EXCLUDED.target_completion_date,
                        is_ignored = false,
                        ignored_at = NULL,
                        ignored_by = NULL,
                        ignore_reason = NULL,
                        plan_status = 'active',
                        created_by = EXCLUDED.created_by,
                        created_at = NOW()
                    RETURNING id, customer_id, iso_standard_id
                """, request.customer_id, request.iso_standard_id, request.plan_name,
                    request.target_completion_date, user.get("user_id"))

                plan_id = plan_row['id']
                logger.info(f"Step 1/3: Plan created or reactivated: {plan_id}")

                # Step 4.5: Clean up old template assignments and tasks if plan was reactivated
                # (This handles the case where a deleted plan is being reused)
                await conn.execute("""
                    DELETE FROM dna_app.customer_iso_plan_templates
                    WHERE plan_id = $1
                """, plan_id)

                await conn.execute("""
                    DELETE FROM dna_app.customer_tasks
                    WHERE plan_id = $1
                """, plan_id)

                logger.info(f"Step 1.5/3: Cleaned up old template assignments and tasks for plan {plan_id}")

                # Step 5: Validate and add templates
                templates_added = 0
                for template_id in request.template_ids:
                    # Validate template exists
                    template_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM dna_app.templates WHERE id = $1)",
                        template_id
                    )
                    if not template_exists:
                        raise HTTPException(404, f"Template {template_id} not found")

                    # Add template to plan
                    await conn.execute("""
                        INSERT INTO dna_app.customer_iso_plan_templates (
                            plan_id, template_id
                        ) VALUES ($1, $2)
                    """, plan_id, template_id)
                    templates_added += 1

                logger.info(f"Step 2/3: Added {templates_added} templates to plan {plan_id}")

                # Step 6: Generate tasks from all templates
                template_rows = await conn.fetch("""
                    SELECT t.id, t.name, t.template_structure
                    FROM dna_app.templates t
                    JOIN dna_app.customer_iso_plan_templates cipt
                        ON t.id = cipt.template_id
                    WHERE cipt.plan_id = $1
                """, plan_id)

                if not template_rows:
                    raise HTTPException(400, "No templates found in plan")

                total_tasks = 0
                for template_row in template_rows:
                    template_structure = template_row['template_structure']

                    # Parse JSON if string
                    if isinstance(template_structure, str):
                        template_structure = json.loads(template_structure)

                    fillable_sections = template_structure.get('fillable_sections', [])

                    for section in fillable_sections:
                        # Create task
                        await conn.execute("""
                            INSERT INTO dna_app.customer_tasks (
                                customer_id, plan_id, task_type, task_scope,
                                section_id, title, description, priority,
                                requires_evidence, evidence_description,
                                auto_generated, status, due_date
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                                      CURRENT_DATE + ($13 * INTERVAL '1 day'))
                        """,
                            request.customer_id,
                            plan_id,
                            'answer_question',
                            'question',
                            section.get('id'),
                            section.get('title', 'Untitled Question'),
                            section.get('question_context', ''),
                            section.get('priority', 'medium'),
                            section.get('requires_evidence', False),
                            section.get('evidence_description', ''),
                            True,
                            'pending',
                            request.due_date_offset_days
                        )
                        total_tasks += 1

                logger.info(f"Step 3/3: Generated {total_tasks} tasks for plan {plan_id}")

                # Success - transaction commits automatically
                return PlanCreateCompleteResponse(
                    plan_id=plan_id,
                    customer_id=request.customer_id,
                    iso_standard_id=request.iso_standard_id,
                    iso_code=iso_row['code'],
                    iso_name=iso_row['name'],
                    templates_added=templates_added,
                    tasks_created=total_tasks,
                    message=f"Plan created successfully with {templates_added} templates and {total_tasks} tasks"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating complete plan: {e}")
        raise HTTPException(500, f"Failed to create plan: {str(e)}")


@router.post("/plans", response_model=PlanResponse)
async def create_plan(
    plan: PlanCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create new ISO plan for customer.

    This assigns an ISO standard to a customer but doesn't add templates yet.
    Use POST /plans/{id}/templates to add templates.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Check if customer exists
            customer_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM dna_app.customers WHERE id = $1)",
                plan.customer_id
            )
            if not customer_exists:
                raise HTTPException(404, "Customer not found")

            # Check if ISO exists
            iso_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM dna_app.iso_standards WHERE id = $1)",
                plan.iso_standard_id
            )
            if not iso_exists:
                raise HTTPException(404, "ISO standard not found")

            # Create plan
            row = await conn.fetchrow("""
                INSERT INTO dna_app.customer_iso_plans (
                    customer_id, iso_standard_id, plan_name,
                    target_completion_date, created_by
                ) VALUES ($1, $2, $3, $4, $5)
                RETURNING id, customer_id, iso_standard_id, plan_name,
                          plan_status, target_completion_date, created_at
            """, plan.customer_id, plan.iso_standard_id, plan.plan_name,
                plan.target_completion_date, user.get("user_id"))

            # Get ISO details
            iso_row = await conn.fetchrow("""
                SELECT code, name FROM dna_app.iso_standards WHERE id = $1
            """, plan.iso_standard_id)

            logger.info(f"Plan created: {row['id']} for customer {plan.customer_id}")

            return PlanResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                iso_standard_id=row['iso_standard_id'],
                iso_code=iso_row['code'],
                iso_name=iso_row['name'],
                plan_name=row['plan_name'],
                plan_status=row['plan_status'],
                target_completion_date=row['target_completion_date'],
                created_at=row['created_at']
            )

    except asyncpg.UniqueViolationError:
        raise HTTPException(400, "Customer already has an active plan for this ISO standard")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        raise HTTPException(500, f"Failed to create plan: {str(e)}")


@router.get("/customers/{customer_id}/plans", response_model=List[PlanResponse])
async def list_customer_plans(
    customer_id: int,
    include_ignored: bool = Query(False),
    user: dict = Depends(get_current_user)
):
    """
    List all ISO plans for a customer.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Check if customer exists
            customer_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM dna_app.customers WHERE id = $1)",
                customer_id
            )
            if not customer_exists:
                raise HTTPException(404, "Customer not found")

            # Build query
            ignored_filter = "" if include_ignored else "AND (cip.is_ignored = false OR cip.is_ignored IS NULL)"

            rows = await conn.fetch(f"""
                SELECT
                    cip.id, cip.customer_id, cip.iso_standard_id, cip.plan_name,
                    cip.plan_status, cip.target_completion_date, cip.created_at,
                    iso.code as iso_code, iso.name as iso_name,

                    -- Progress from view
                    COALESCE(v.total_templates, 0) as total_templates,
                    COALESCE(v.completed_templates, 0) as completed_templates,
                    COALESCE(v.total_tasks, 0) as total_tasks,
                    COALESCE(v.completed_tasks, 0) as completed_tasks,
                    COALESCE(v.progress_percentage, 0) as progress_percentage

                FROM dna_app.customer_iso_plans cip
                JOIN dna_app.iso_standards iso ON cip.iso_standard_id = iso.id
                LEFT JOIN dna_app.v_customer_iso_progress v
                    ON cip.id = v.id
                WHERE cip.customer_id = $1 {ignored_filter}
                ORDER BY cip.created_at DESC
            """, customer_id)

            return [
                PlanResponse(
                    id=row['id'],
                    customer_id=row['customer_id'],
                    iso_standard_id=row['iso_standard_id'],
                    iso_code=row['iso_code'],
                    iso_name=row['iso_name'],
                    plan_name=row['plan_name'],
                    plan_status=row['plan_status'],
                    target_completion_date=row['target_completion_date'],
                    created_at=row['created_at'],
                    total_templates=row['total_templates'],
                    completed_templates=row['completed_templates'],
                    total_tasks=row['total_tasks'],
                    completed_tasks=row['completed_tasks'],
                    progress_percentage=row['progress_percentage']
                )
                for row in rows
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing plans: {e}")
        raise HTTPException(500, f"Failed to list plans: {str(e)}")


@router.post("/plans/{plan_id}/templates")
async def add_templates_to_plan(
    plan_id: UUID,
    assignment: TemplateAssignment,
    user: dict = Depends(get_current_user)
):
    """
    Add templates to a plan.

    Templates must be associated with the plan's ISO standard.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get plan details
                plan_row = await conn.fetchrow("""
                    SELECT customer_id, iso_standard_id
                    FROM dna_app.customer_iso_plans
                    WHERE id = $1
                """, plan_id)

                if not plan_row:
                    raise HTTPException(404, "Plan not found")

                # Insert template assignments
                added_count = 0
                for template_id in assignment.template_ids:
                    # Check if template is associated with this ISO
                    template_iso_valid = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM dna_app.template_iso_mapping
                            WHERE template_id = $1 AND iso_standard_id = $2
                        )
                    """, template_id, plan_row['iso_standard_id'])

                    if not template_iso_valid:
                        logger.warning(f"Template {template_id} not associated with ISO {plan_row['iso_standard_id']}")
                        continue

                    # Add to plan (skip if already exists)
                    try:
                        await conn.execute("""
                            INSERT INTO dna_app.customer_iso_plan_templates (
                                plan_id, template_id
                            ) VALUES ($1, $2)
                            ON CONFLICT DO NOTHING
                        """, plan_id, template_id)
                        added_count += 1
                    except:
                        logger.warning(f"Failed to add template {template_id} to plan {plan_id}")

                logger.info(f"Added {added_count} templates to plan {plan_id}")

                return {
                    "message": f"Successfully added {added_count} templates to plan",
                    "plan_id": str(plan_id),
                    "templates_added": added_count
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding templates to plan: {e}")
        raise HTTPException(500, f"Failed to add templates: {str(e)}")


@router.delete("/plans/{plan_id}/templates/{template_id}")
async def remove_template_from_plan(
    plan_id: UUID,
    template_id: UUID,
    reason: Optional[str] = Query(None, description="Reason for removal"),
    user: dict = Depends(get_current_user)
):
    """
    Remove template from plan (marks as ignored, not deleted).

    This will also mark all related tasks as ignored.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Mark plan template as ignored
                result = await conn.fetchval("""
                    UPDATE dna_app.customer_iso_plan_templates
                    SET is_ignored = true, ignored_at = NOW(),
                        ignored_by = $3, ignore_reason = $4
                    WHERE plan_id = $1 AND template_id = $2
                    RETURNING plan_id
                """, plan_id, template_id, user.get("user_id"), reason or "Removed by admin")

                if not result:
                    raise HTTPException(404, "Template assignment not found in this plan")

                # Mark all related tasks as ignored
                tasks_updated = await conn.fetchval("""
                    UPDATE dna_app.customer_tasks ct
                    SET is_ignored = true, ignored_at = NOW(),
                        ignored_by = $3, ignore_reason = $4
                    FROM dna_app.customer_documents cd
                    WHERE ct.document_id = cd.id
                      AND cd.plan_id = $1
                      AND cd.template_id = $2
                      AND (ct.is_ignored = false OR ct.is_ignored IS NULL)
                    RETURNING COUNT(*)
                """, plan_id, template_id, user.get("user_id"), reason or "Template removed from plan")

                logger.info(f"Removed template {template_id} from plan {plan_id}, marked {tasks_updated or 0} tasks as ignored")

                return {
                    "message": "Template removed from plan successfully",
                    "plan_id": str(plan_id),
                    "template_id": str(template_id),
                    "tasks_ignored": tasks_updated or 0
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing template from plan: {e}")
        raise HTTPException(500, f"Failed to remove template: {str(e)}")


@router.post("/plans/{plan_id}/generate-tasks", response_model=TaskGenerationResponse)
async def generate_tasks_from_templates(
    plan_id: UUID,
    request: TaskGenerationRequest,
    user: dict = Depends(get_current_user)
):
    """
    Generate tasks from all templates in the plan.

    Creates one task per fillable_section (question) in each template.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get plan details
                plan_row = await conn.fetchrow("""
                    SELECT customer_id, iso_standard_id
                    FROM dna_app.customer_iso_plans
                    WHERE id = $1
                """, plan_id)

                if not plan_row:
                    raise HTTPException(404, "Plan not found")

                # Get all templates in the plan
                template_rows = await conn.fetch("""
                    SELECT t.id, t.name, t.template_structure
                    FROM dna_app.templates t
                    JOIN dna_app.customer_iso_plan_templates cipt
                        ON t.id = cipt.template_id
                    WHERE cipt.plan_id = $1
                      AND (cipt.is_ignored = false OR cipt.is_ignored IS NULL)
                """, plan_id)

                if not template_rows:
                    raise HTTPException(400, "No templates found in this plan")

                tasks_by_template = {}
                total_tasks = 0

                # For each template, generate tasks from fillable_sections
                for template_row in template_rows:
                    template_id = template_row['id']
                    template_name = template_row['name']
                    template_structure = template_row['template_structure']

                    # Parse JSON if it's a string
                    if isinstance(template_structure, str):
                        template_structure = json.loads(template_structure)

                    fillable_sections = template_structure.get('fillable_sections', [])
                    tasks_created = 0

                    for section in fillable_sections:
                        # Create task for this question
                        task_row = await conn.fetchrow("""
                            INSERT INTO dna_app.customer_tasks (
                                customer_id, plan_id, task_type, task_scope,
                                section_id, title, description, priority,
                                requires_evidence, evidence_description,
                                auto_generated, status, due_date
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                                      CURRENT_DATE + ($13 * INTERVAL '1 day'))
                            RETURNING id
                        """,
                            plan_row['customer_id'],
                            plan_id,
                            'answer_question',
                            'question',
                            section.get('id'),
                            section.get('title', 'Untitled Question'),
                            section.get('question_context', ''),
                            section.get('priority', 'medium'),
                            section.get('requires_evidence', False),
                            section.get('evidence_description', ''),
                            True,  # auto_generated
                            'pending',
                            request.due_date_offset_days
                        )

                        if task_row:
                            tasks_created += 1
                            total_tasks += 1

                    tasks_by_template[template_name] = tasks_created

                logger.info(f"Generated {total_tasks} tasks for plan {plan_id}")

                return TaskGenerationResponse(
                    plan_id=plan_id,
                    total_templates=len(template_rows),
                    total_tasks_generated=total_tasks,
                    tasks_by_template=tasks_by_template
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating tasks: {e}")
        raise HTTPException(500, f"Failed to generate tasks: {str(e)}")


@router.patch("/plans/{plan_id}/ignore")
async def ignore_plan(
    plan_id: UUID,
    reason: Optional[str] = Query(None, description="Reason for ignoring"),
    user: dict = Depends(get_current_user)
):
    """
    Mark plan as ignored (soft delete, kept for audit trail).

    This will also:
    - Mark all related tasks as ignored
    - Set task status to 'cancelled' for reporting
    - Mark template assignments as ignored
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check if plan exists
                plan_exists = await conn.fetchval("""
                    SELECT EXISTS(SELECT 1 FROM dna_app.customer_iso_plans WHERE id = $1)
                """, plan_id)

                if not plan_exists:
                    raise HTTPException(404, "Plan not found")

                # Mark plan as ignored and set status to cancelled
                await conn.execute("""
                    UPDATE dna_app.customer_iso_plans
                    SET is_ignored = true,
                        ignored_at = NOW(),
                        ignored_by = $2,
                        ignore_reason = $3,
                        plan_status = 'cancelled'
                    WHERE id = $1
                """, plan_id, user.get("user_id"), reason or "Plan deleted by admin")

                # Mark template assignments as ignored
                await conn.execute("""
                    UPDATE dna_app.customer_iso_plan_templates
                    SET is_ignored = true, ignored_at = NOW(),
                        ignored_by = $2, ignore_reason = $3
                    WHERE plan_id = $1
                      AND (is_ignored = false OR is_ignored IS NULL)
                """, plan_id, user.get("user_id"), reason or "Plan deleted")

                # Mark all related tasks as ignored AND cancelled
                result = await conn.execute("""
                    UPDATE dna_app.customer_tasks
                    SET is_ignored = true,
                        ignored_at = NOW(),
                        ignored_by = $2,
                        ignore_reason = $3,
                        status = 'cancelled',
                        updated_at = NOW()
                    WHERE plan_id = $1
                      AND (is_ignored = false OR is_ignored IS NULL)
                      AND status != 'cancelled'
                """, plan_id, user.get("user_id"), reason or "Plan deleted")

                # Extract count from result string (e.g., "UPDATE 7")
                tasks_updated = int(result.split()[-1]) if result else 0

                logger.info(f"Plan {plan_id} deleted (soft), {tasks_updated or 0} tasks cancelled")

                return {
                    "message": "Plan deleted successfully",
                    "plan_id": str(plan_id),
                    "tasks_cancelled": tasks_updated or 0
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting plan: {e}")
        raise HTTPException(500, f"Failed to delete plan: {str(e)}")


# =====================================================
# Task Management Endpoints
# =====================================================

class TaskResponse(BaseModel):
    """Task response model."""
    id: UUID
    customer_id: int
    plan_id: UUID
    document_id: Optional[UUID] = None
    task_type: str
    task_scope: str
    section_id: str
    title: str
    description: Optional[str]
    priority: str
    status: str
    requires_evidence: bool
    evidence_description: Optional[str]
    auto_generated: bool
    due_date: Optional[date]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    # Related info
    plan_iso_name: Optional[str] = None
    document_name: Optional[str] = None
    template_name: Optional[str] = None
    plan_iso_code: Optional[str] = None


class TaskUpdate(BaseModel):
    """Update task model."""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


@router.get("/customers/{customer_id}/tasks", response_model=List[TaskResponse])
async def list_customer_tasks(
    customer_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    plan_id: Optional[UUID] = Query(None, description="Filter by plan"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    include_ignored: bool = Query(False, description="Include ignored tasks"),
    user: dict = Depends(get_current_user)
):
    """
    List all tasks for a customer with optional filters.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Check customer exists
            customer_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM dna_app.customers WHERE id = $1)",
                customer_id
            )
            if not customer_exists:
                raise HTTPException(404, "Customer not found")

            # Build query with filters
            conditions = ["ct.customer_id = $1"]
            params = [customer_id]
            param_count = 1

            if not include_ignored:
                conditions.append("(ct.is_ignored = false OR ct.is_ignored IS NULL)")

            if status:
                param_count += 1
                conditions.append(f"ct.status = ${param_count}")
                params.append(status)

            if plan_id:
                param_count += 1
                conditions.append(f"ct.plan_id = ${param_count}")
                params.append(plan_id)

            if priority:
                param_count += 1
                conditions.append(f"ct.priority = ${param_count}")
                params.append(priority)

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    ct.id, ct.customer_id, ct.plan_id, ct.document_id, ct.task_type, ct.task_scope,
                    ct.section_id, ct.title, ct.description, ct.priority, ct.status,
                    ct.requires_evidence, ct.evidence_description, ct.auto_generated,
                    ct.due_date, ct.completed_at, ct.created_at, ct.updated_at,
                    iso.name as plan_iso_name, iso.code as plan_iso_code,
                    cd.document_name, cd.template_name
                FROM dna_app.customer_tasks ct
                LEFT JOIN dna_app.customer_iso_plans cip ON ct.plan_id = cip.id
                LEFT JOIN dna_app.iso_standards iso ON cip.iso_standard_id = iso.id
                LEFT JOIN dna_app.customer_documents cd ON ct.document_id = cd.id
                WHERE {where_clause}
                ORDER BY
                    CASE ct.status
                        WHEN 'pending' THEN 1
                        WHEN 'in_progress' THEN 2
                        WHEN 'completed' THEN 3
                        WHEN 'cancelled' THEN 4
                    END,
                    ct.due_date ASC NULLS LAST,
                    ct.created_at DESC
            """

            rows = await conn.fetch(query, *params)

            return [
                TaskResponse(
                    id=row['id'],
                    customer_id=row['customer_id'],
                    plan_id=row['plan_id'],
                    document_id=row['document_id'],
                    task_type=row['task_type'],
                    task_scope=row['task_scope'],
                    section_id=row['section_id'],
                    title=row['title'],
                    description=row['description'],
                    priority=row['priority'],
                    status=row['status'],
                    requires_evidence=row['requires_evidence'],
                    evidence_description=row['evidence_description'],
                    auto_generated=row['auto_generated'],
                    due_date=row['due_date'],
                    completed_at=row['completed_at'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    plan_iso_name=row['plan_iso_name'],
                    plan_iso_code=row['plan_iso_code'],
                    document_name=row['document_name'],
                    template_name=row['template_name']
                )
                for row in rows
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(500, f"Failed to list tasks: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """
    Get single task details.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    ct.id, ct.customer_id, ct.plan_id, ct.task_type, ct.task_scope,
                    ct.section_id, ct.title, ct.description, ct.priority, ct.status,
                    ct.requires_evidence, ct.evidence_description, ct.auto_generated,
                    ct.due_date, ct.completed_at, ct.created_at, ct.updated_at,
                    iso.name as plan_iso_name, iso.code as plan_iso_code
                FROM dna_app.customer_tasks ct
                LEFT JOIN dna_app.customer_iso_plans cip ON ct.plan_id = cip.id
                LEFT JOIN dna_app.iso_standards iso ON cip.iso_standard_id = iso.id
                WHERE ct.id = $1
            """, task_id)

            if not row:
                raise HTTPException(404, "Task not found")

            return TaskResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                plan_id=row['plan_id'],
                task_type=row['task_type'],
                task_scope=row['task_scope'],
                section_id=row['section_id'],
                title=row['title'],
                description=row['description'],
                priority=row['priority'],
                status=row['status'],
                requires_evidence=row['requires_evidence'],
                evidence_description=row['evidence_description'],
                auto_generated=row['auto_generated'],
                due_date=row['due_date'],
                completed_at=row['completed_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                plan_iso_name=row['plan_iso_name'],
                plan_iso_code=row['plan_iso_code']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(500, f"Failed to get task: {str(e)}")


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update task details.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check task exists
                task_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM dna_app.customer_tasks WHERE id = $1)",
                    task_id
                )
                if not task_exists:
                    raise HTTPException(404, "Task not found")

                # Build update query dynamically
                updates = []
                params = [task_id]
                param_count = 1

                if task_update.title is not None:
                    param_count += 1
                    updates.append(f"title = ${param_count}")
                    params.append(task_update.title)

                if task_update.description is not None:
                    param_count += 1
                    updates.append(f"description = ${param_count}")
                    params.append(task_update.description)

                if task_update.priority is not None:
                    param_count += 1
                    updates.append(f"priority = ${param_count}")
                    params.append(task_update.priority)

                if task_update.status is not None:
                    param_count += 1
                    updates.append(f"status = ${param_count}")
                    params.append(task_update.status)

                    # If marking as completed, set completed_at
                    if task_update.status == 'completed':
                        updates.append("completed_at = NOW()")

                if task_update.due_date is not None:
                    param_count += 1
                    updates.append(f"due_date = ${param_count}")
                    params.append(task_update.due_date)

                # Always update updated_at
                updates.append("updated_at = NOW()")

                if not updates:
                    raise HTTPException(400, "No fields to update")

                set_clause = ", ".join(updates)
                query = f"""
                    UPDATE dna_app.customer_tasks
                    SET {set_clause}
                    WHERE id = $1
                    RETURNING id
                """

                await conn.execute(query, *params)

                logger.info(f"Task {task_id} updated by user {user.get('user_id')}")

                # Return updated task
                return await get_task(task_id, user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(500, f"Failed to update task: {str(e)}")


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """
    Mark task as completed.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check task exists and get details
                task_row = await conn.fetchrow("""
                    SELECT id, status, requires_evidence
                    FROM dna_app.customer_tasks
                    WHERE id = $1
                """, task_id)

                if not task_row:
                    raise HTTPException(404, "Task not found")

                if task_row['status'] == 'completed':
                    raise HTTPException(400, "Task is already completed")

                # TODO: Check if evidence is required and uploaded
                # if task_row['requires_evidence']:
                #     evidence_count = await conn.fetchval(
                #         "SELECT COUNT(*) FROM task_evidence WHERE task_id = $1",
                #         task_id
                #     )
                #     if evidence_count == 0:
                #         raise HTTPException(400, "Evidence is required to complete this task")

                # Mark as completed
                await conn.execute("""
                    UPDATE dna_app.customer_tasks
                    SET status = 'completed',
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                """, task_id)

                logger.info(f"Task {task_id} completed by user {user.get('user_id')}")

                return {
                    "message": "Task completed successfully",
                    "task_id": str(task_id),
                    "completed_at": datetime.now().isoformat()
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        raise HTTPException(500, f"Failed to complete task: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    user: dict = Depends(get_current_user)
):
    """
    Cancel a task (mark as no longer relevant).
    Task status set to 'cancelled', but not ignored - remains visible for audit.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check task exists
                task_row = await conn.fetchrow("""
                    SELECT id, status FROM dna_app.customer_tasks
                    WHERE id = $1
                """, task_id)

                if not task_row:
                    raise HTTPException(404, "Task not found")

                if task_row['status'] == 'cancelled':
                    raise HTTPException(400, "Task is already cancelled")

                # Mark as cancelled
                await conn.execute("""
                    UPDATE dna_app.customer_tasks
                    SET status = 'cancelled',
                        updated_at = NOW()
                    WHERE id = $1
                """, task_id)

                logger.info(f"Task {task_id} cancelled by user {user.get('user_id')}: {reason or 'No reason provided'}")

                return {
                    "message": "Task cancelled successfully",
                    "task_id": str(task_id),
                    "reason": reason or "No reason provided"
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(500, f"Failed to cancel task: {str(e)}")


@router.post("/tasks/{task_id}/hold")
async def put_task_on_hold(
    task_id: UUID,
    reason: Optional[str] = Query(None, description="Reason for putting on hold"),
    user: dict = Depends(get_current_user)
):
    """
    Put a task on hold (status = 'on_hold').
    Task remains visible but marked as temporarily paused.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check task exists
                task_row = await conn.fetchrow("""
                    SELECT id, status FROM dna_app.customer_tasks
                    WHERE id = $1
                """, task_id)

                if not task_row:
                    raise HTTPException(404, "Task not found")

                if task_row['status'] == 'on_hold':
                    raise HTTPException(400, "Task is already on hold")

                # Put on hold
                await conn.execute("""
                    UPDATE dna_app.customer_tasks
                    SET status = 'on_hold',
                        updated_at = NOW()
                    WHERE id = $1
                """, task_id)

                logger.info(f"Task {task_id} put on hold by user {user.get('user_id')}: {reason or 'No reason provided'}")

                return {
                    "message": "Task put on hold successfully",
                    "task_id": str(task_id),
                    "reason": reason or "On hold"
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error putting task on hold: {e}")
        raise HTTPException(500, f"Failed to put task on hold: {str(e)}")

# =====================================================
# Documents Endpoints
# =====================================================

class DocumentResponse(BaseModel):
    """Document response model."""
    id: UUID
    customer_id: int
    plan_id: UUID
    template_id: UUID
    template_name: str
    document_name: str
    document_type: Optional[str]
    iso_code: Optional[str]
    status: str
    completion_percentage: int
    created_at: datetime
    
    # Task stats
    total_tasks: int = 0
    completed_tasks: int = 0


class PlanTemplateResponse(BaseModel):
    """Plan template response with task stats."""
    id: UUID  # template_id
    plan_id: UUID
    template_name: str
    template_description: Optional[str]
    iso_code: Optional[str]
    total_tasks: int = 0
    completed_tasks: int = 0


@router.get("/customers/{customer_id}/plan-templates", response_model=List[PlanTemplateResponse])
async def list_customer_plan_templates(
    customer_id: int,
    user: dict = Depends(get_current_user)
):
    """
    List all templates assigned to customer's plans with task statistics.
    This shows ISO → Templates → Tasks relationship.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Check customer exists
            customer_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM dna_app.customers WHERE id = $1)",
                customer_id
            )
            if not customer_exists:
                raise HTTPException(404, "Customer not found")

            # Get templates assigned to customer's plans with task counts
            query = """
                SELECT
                    t.id as template_id,
                    cipt.plan_id,
                    t.name as template_name,
                    t.description as template_description,
                    iso.code as iso_code,
                    COUNT(ct.id) FILTER (
                        WHERE ct.plan_id = cipt.plan_id
                        AND (ct.is_ignored IS NOT TRUE OR ct.is_ignored IS NULL)
                    ) as total_tasks,
                    COUNT(ct.id) FILTER (
                        WHERE ct.plan_id = cipt.plan_id
                        AND ct.status = 'completed'
                        AND (ct.is_ignored IS NOT TRUE OR ct.is_ignored IS NULL)
                    ) as completed_tasks
                FROM dna_app.customer_iso_plan_templates cipt
                JOIN dna_app.templates t ON cipt.template_id = t.id
                JOIN dna_app.customer_iso_plans cip ON cipt.plan_id = cip.id
                JOIN dna_app.iso_standards iso ON cip.iso_standard_id = iso.id
                LEFT JOIN dna_app.customer_tasks ct ON ct.plan_id = cipt.plan_id
                WHERE cip.customer_id = $1
                  AND (cipt.is_ignored IS NOT TRUE OR cipt.is_ignored IS NULL)
                  AND (cip.is_ignored IS NOT TRUE OR cip.is_ignored IS NULL)
                GROUP BY t.id, cipt.plan_id, t.name, t.description, iso.code
                ORDER BY cipt.plan_id, t.name
            """

            rows = await conn.fetch(query, customer_id)

            return [
                PlanTemplateResponse(
                    id=row['template_id'],
                    plan_id=row['plan_id'],
                    template_name=row['template_name'],
                    template_description=row['template_description'],
                    iso_code=row['iso_code'],
                    total_tasks=row['total_tasks'] or 0,
                    completed_tasks=row['completed_tasks'] or 0
                )
                for row in rows
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing plan templates: {e}")
        raise HTTPException(500, f"Failed to list plan templates: {str(e)}")
