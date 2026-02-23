"""
ISO Plans Management API
========================

Manage customer ISO certification plans and document generation.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime, date
import asyncio

from ..database import get_db_pool
from ..auth import get_current_user, require_admin
from ..config import settings
from ..services.document_generator_service import generate_documents_for_plan
from ..services.task_generator_service import generate_tasks_for_document, generate_customer_level_tasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iso-plans", tags=["ISO Plans"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ISOPlanCreate(BaseModel):
    """Create ISO plan"""
    customer_id: int
    iso_standard_id: UUID
    plan_name: Optional[str] = None
    template_selection_mode: str = Field("all", description="'all' or 'selective'")
    selected_template_ids: Optional[List[UUID]] = None
    target_completion_date: Optional[date] = None
    auto_generate_documents: bool = Field(False, description="Generate documents immediately")


class ISOPlanUpdate(BaseModel):
    """Update ISO plan"""
    plan_name: Optional[str] = None
    plan_status: Optional[str] = None
    target_completion_date: Optional[date] = None


class TemplatePreview(BaseModel):
    """Template preview for generation"""
    id: UUID
    name: str
    version_number: int
    document_type: str
    estimated_tasks: int


class ISOPlanResponse(BaseModel):
    """ISO plan response"""
    id: UUID
    customer_id: int
    iso_standard_id: UUID
    iso_code: str
    iso_name: str
    plan_name: Optional[str]
    plan_status: str
    template_selection_mode: str
    documents_generated: bool
    document_count: int
    task_count: int
    target_completion_date: Optional[date]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerationPreview(BaseModel):
    """Preview what will be generated"""
    iso_plan_id: UUID
    iso_code: str
    iso_name: str
    templates: List[TemplatePreview]
    total_documents: int
    estimated_tasks: int
    estimated_time_seconds: int


class GenerationProgress(BaseModel):
    """Real-time generation progress"""
    status: str  # generating, completed, failed
    current_step: str
    documents_created: int
    total_documents: int
    tasks_created: int
    progress_percentage: int
    message: str


class GenerationResult(BaseModel):
    """Document generation result"""
    iso_plan_id: UUID
    documents_created: int
    tasks_created: int
    duration_seconds: float
    status: str
    message: str


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("", response_model=ISOPlanResponse, status_code=201)
async def create_iso_plan(
    plan_data: ISOPlanCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin)
):
    """
    Create ISO plan for customer.

    Optionally auto-generate documents if auto_generate_documents=True.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if customer exists
            customer = await conn.fetchrow(
                f"SELECT id, name FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
                plan_data.customer_id
            )
            if not customer:
                raise HTTPException(404, f"Customer {plan_data.customer_id} not found")

            # Check if ISO standard exists
            iso_standard = await conn.fetchrow(
                f"SELECT id, code, name FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1",
                plan_data.iso_standard_id
            )
            if not iso_standard:
                raise HTTPException(404, f"ISO standard {plan_data.iso_standard_id} not found")

            # Check if plan already exists
            existing_plan = await conn.fetchrow(
                f"""SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans
                   WHERE customer_id = $1 AND iso_standard_id = $2""",
                plan_data.customer_id, plan_data.iso_standard_id
            )
            if existing_plan:
                raise HTTPException(
                    400,
                    f"ISO plan already exists for this customer. Plan ID: {existing_plan['id']}"
                )

            # Generate plan name if not provided
            if not plan_data.plan_name:
                plan_name = f"{iso_standard['code']} Certification {datetime.now().year}"
            else:
                plan_name = plan_data.plan_name

            # Create ISO plan
            plan_row = await conn.fetchrow(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_iso_plans (
                    customer_id, iso_standard_id, plan_name, plan_status,
                    template_selection_mode, target_completion_date,
                    started_at, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, customer_id, iso_standard_id, plan_name, plan_status,
                          template_selection_mode, target_completion_date,
                          started_at, completed_at, created_at, updated_at
            """, plan_data.customer_id, plan_data.iso_standard_id, plan_name, 'assigned',
                plan_data.template_selection_mode, plan_data.target_completion_date,
                datetime.now(), current_user.get('user_id'))

            plan_id = plan_row['id']

            # If selective mode, save selected templates
            if plan_data.template_selection_mode == 'selective' and plan_data.selected_template_ids:
                for template_id in plan_data.selected_template_ids:
                    await conn.execute(f"""
                        INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_iso_plan_templates
                        (plan_id, template_id, included)
                        VALUES ($1, $2, $3)
                    """, plan_id, template_id, True)

            logger.info(
                f"Created ISO plan {plan_id} for customer {plan_data.customer_id} "
                f"(ISO: {iso_standard['code']}) by user {current_user.get('user_id')}"
            )

            # Build response
            result = dict(plan_row)
            result['iso_code'] = iso_standard['code']
            result['iso_name'] = iso_standard['name']
            result['documents_generated'] = False
            result['document_count'] = 0
            result['task_count'] = 0

            # Auto-generate documents if requested
            if plan_data.auto_generate_documents:
                # Run in background
                background_tasks.add_task(
                    generate_documents_for_plan,
                    plan_id,
                    plan_data.customer_id,
                    plan_data.iso_standard_id,
                    plan_data.template_selection_mode,
                    plan_data.selected_template_ids
                )
                result['documents_generated'] = True  # Will be generated
                logger.info(f"Queued document generation for plan {plan_id}")

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating ISO plan: {e}")
        raise HTTPException(500, f"Failed to create ISO plan: {str(e)}")


@router.get("/customer/{customer_id}", response_model=List[ISOPlanResponse])
async def list_customer_iso_plans(
    customer_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    List all ISO plans for a customer.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT
                    p.id, p.customer_id, p.iso_standard_id, p.plan_name, p.plan_status,
                    p.template_selection_mode, p.target_completion_date,
                    p.started_at, p.completed_at, p.created_at, p.updated_at,
                    iso.code as iso_code, iso.name as iso_name,
                    COUNT(DISTINCT d.id) > 0 as documents_generated,
                    COUNT(DISTINCT d.id) as document_count,
                    COUNT(DISTINCT t.id) as task_count
                FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
                INNER JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON p.iso_standard_id = iso.id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents d ON p.id = d.plan_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_tasks t ON d.id = t.document_id OR t.plan_id = p.id
                WHERE p.customer_id = $1
                GROUP BY p.id, iso.code, iso.name
                ORDER BY p.created_at DESC
            """

            rows = await conn.fetch(query, customer_id)
            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error listing ISO plans for customer {customer_id}: {e}")
        raise HTTPException(500, f"Failed to list ISO plans: {str(e)}")


@router.get("/{plan_id}", response_model=ISOPlanResponse)
async def get_iso_plan(
    plan_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get ISO plan by ID.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT
                    p.id, p.customer_id, p.iso_standard_id, p.plan_name, p.plan_status,
                    p.template_selection_mode, p.target_completion_date,
                    p.started_at, p.completed_at, p.created_at, p.updated_at,
                    iso.code as iso_code, iso.name as iso_name,
                    COUNT(DISTINCT d.id) > 0 as documents_generated,
                    COUNT(DISTINCT d.id) as document_count,
                    COUNT(DISTINCT t.id) as task_count
                FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
                INNER JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON p.iso_standard_id = iso.id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents d ON p.id = d.plan_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_tasks t ON d.id = t.document_id OR t.plan_id = p.id
                WHERE p.id = $1
                GROUP BY p.id, iso.code, iso.name
            """

            row = await conn.fetchrow(query, plan_id)

            if not row:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ISO plan {plan_id}: {e}")
        raise HTTPException(500, f"Failed to get ISO plan: {str(e)}")


@router.get("/{plan_id}/generation-preview", response_model=GenerationPreview)
async def get_generation_preview(
    plan_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get preview of what will be generated for this ISO plan.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Get plan details
            plan = await conn.fetchrow(
                f"""SELECT p.*, iso.code as iso_code, iso.name as iso_name
                   FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
                   INNER JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON p.iso_standard_id = iso.id
                   WHERE p.id = $1""",
                plan_id
            )

            if not plan:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            # Get templates
            if plan['template_selection_mode'] == 'all':
                templates_query = f"""
                    SELECT t.id, t.name, t.version_number, t.document_type,
                           COALESCE(jsonb_array_length(t.fillable_sections), 0) * 2 as estimated_tasks
                    FROM {settings.DATABASE_APP_SCHEMA}.templates t
                    INNER JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping tim ON t.id = tim.template_id
                    WHERE tim.iso_standard_id = $1 AND t.status = 'active'
                    ORDER BY t.name
                """
                templates = await conn.fetch(templates_query, plan['iso_standard_id'])
            else:
                templates_query = f"""
                    SELECT t.id, t.name, t.version_number, t.document_type,
                           COALESCE(jsonb_array_length(t.fillable_sections), 0) * 2 as estimated_tasks
                    FROM {settings.DATABASE_APP_SCHEMA}.templates t
                    INNER JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plan_templates pt ON t.id = pt.template_id
                    WHERE pt.plan_id = $1 AND pt.included = true AND t.status = 'active'
                    ORDER BY t.name
                """
                templates = await conn.fetch(templates_query, plan_id)

            total_tasks = sum(t['estimated_tasks'] for t in templates)
            estimated_time = len(templates) * 0.2  # ~0.2 seconds per document

            return GenerationPreview(
                iso_plan_id=plan_id,
                iso_code=plan['iso_code'],
                iso_name=plan['iso_name'],
                templates=[TemplatePreview(**dict(t)) for t in templates],
                total_documents=len(templates),
                estimated_tasks=total_tasks,
                estimated_time_seconds=int(estimated_time) + 1
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation preview for plan {plan_id}: {e}")
        raise HTTPException(500, f"Failed to get generation preview: {str(e)}")


@router.post("/{plan_id}/generate-documents", response_model=GenerationResult)
async def generate_documents(
    plan_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin)
):
    """
    Generate documents and tasks for an ISO plan.

    This creates all customer documents from templates and auto-generates tasks.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Get plan
            plan = await conn.fetchrow(
                f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE id = $1",
                plan_id
            )

            if not plan:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            # Check if already generated
            existing_docs = await conn.fetchval(
                f"SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE plan_id = $1",
                plan_id
            )

            if existing_docs > 0:
                raise HTTPException(
                    400,
                    f"Documents already generated for this plan ({existing_docs} documents exist). "
                    "Use regenerate endpoint to recreate."
                )

            # Generate documents (synchronously for now, can be moved to background)
            start_time = datetime.now()

            result = await generate_documents_for_plan(
                plan_id=plan_id,
                customer_id=plan['customer_id'],
                iso_standard_id=plan['iso_standard_id'],
                template_selection_mode=plan['template_selection_mode'],
                selected_template_ids=None  # Will be fetched from plan_templates
            )

            duration = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Generated {result['documents_created']} documents and {result['tasks_created']} tasks "
                f"for plan {plan_id} in {duration:.2f}s"
            )

            return GenerationResult(
                iso_plan_id=plan_id,
                documents_created=result['documents_created'],
                tasks_created=result['tasks_created'],
                duration_seconds=duration,
                status='completed',
                message=f"Successfully generated {result['documents_created']} documents and {result['tasks_created']} tasks"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating documents for plan {plan_id}: {e}")
        raise HTTPException(500, f"Failed to generate documents: {str(e)}")


@router.delete("/{plan_id}", status_code=204)
async def delete_iso_plan(
    plan_id: UUID,
    current_user: dict = Depends(require_admin)
):
    """
    Delete ISO plan and all associated documents/tasks.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE id = $1",
                plan_id
            )

            if not existing:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            # Delete plan (cascade will delete documents, tasks, etc.)
            await conn.execute(
                f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE id = $1",
                plan_id
            )

            logger.info(f"Deleted ISO plan {plan_id} by user {current_user.get('user_id')}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ISO plan {plan_id}: {e}")
        raise HTTPException(500, f"Failed to delete ISO plan: {str(e)}")
