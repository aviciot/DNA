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
from ..services.document_generator_service import generate_documents_for_plan, create_customer_document
from ..services.task_generator_service import generate_tasks_for_document, generate_customer_level_tasks, seed_placeholders, reconcile_plan

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
    total_tasks: int = 0
    completed_tasks: int = 0
    answered_tasks: int = 0
    progress_percentage: int = 0
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
                    COUNT(DISTINCT t.id) as task_count,
                    COUNT(DISTINCT t.id) FILTER (
                        WHERE t.status NOT IN ('cancelled')
                          AND (t.is_ignored = false OR t.is_ignored IS NULL)
                    ) as total_tasks,
                    COUNT(DISTINCT t.id) FILTER (
                        WHERE t.status = 'completed'
                          AND (t.is_ignored = false OR t.is_ignored IS NULL)
                    ) as completed_tasks,
                    COUNT(DISTINCT t.id) FILTER (
                        WHERE t.status = 'answered'
                          AND (t.is_ignored = false OR t.is_ignored IS NULL)
                    ) as answered_tasks
                FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
                INNER JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON p.iso_standard_id = iso.id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents d ON p.id = d.plan_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_tasks t ON t.plan_id = p.id
                WHERE p.customer_id = $1
                GROUP BY p.id, iso.code, iso.name
                ORDER BY p.created_at DESC
            """

            rows = await conn.fetch(query, customer_id)
            result = []
            for row in rows:
                r = dict(row)
                total = r.get("total_tasks") or 0
                done = r.get("completed_tasks") or 0
                answered = r.get("answered_tasks") or 0
                r["progress_percentage"] = round((done + answered) / total * 100) if total > 0 else 0
                result.append(r)
            return result

    except Exception as e:
        logger.error(f"Error listing ISO plans for customer {customer_id}: {e}")
        raise HTTPException(500, f"Failed to list ISO plans: {str(e)}")


@router.get("/{plan_id}/documents")
async def list_plan_documents(
    plan_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """List customer documents for a plan."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT d.id, d.template_id, d.plan_id, d.document_name,
                       d.status, d.completion_percentage,
                       t.name as template_name, t.description as template_description,
                       COUNT(DISTINCT ct.id) FILTER (
                           WHERE ct.status NOT IN ('cancelled')
                             AND (ct.is_ignored = false OR ct.is_ignored IS NULL)
                       ) as total_tasks,
                       COUNT(DISTINCT ct.id) FILTER (
                           WHERE ct.status = 'completed'
                             AND (ct.is_ignored = false OR ct.is_ignored IS NULL)
                       ) as completed_tasks
                FROM {settings.DATABASE_APP_SCHEMA}.customer_documents d
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.templates t ON t.id = d.template_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_tasks ct ON
                    ct.plan_id = d.plan_id AND (
                        ct.document_id = d.id
                        OR (ct.placeholder_key IS NOT NULL AND EXISTS (
                            SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.customer_placeholders cp
                            WHERE cp.customer_id = ct.customer_id
                              AND cp.plan_id = ct.plan_id
                              AND cp.placeholder_key = ct.placeholder_key
                              AND d.template_id = ANY(cp.template_ids)
                        ))
                    )
                WHERE d.plan_id = $1
                GROUP BY d.id, t.name, t.description
                ORDER BY d.document_name
            """, plan_id)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listing documents for plan {plan_id}: {e}")
        raise HTTPException(500, str(e))


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


@router.get("/{plan_id}/export-zip")
async def export_plan_zip(
    plan_id: UUID,
    lang: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a ZIP of all customer documents in this plan as PDFs with filled values.
    """
    import io, zipfile, json as _json
    from weasyprint import HTML as WeasyprintHTML
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote
    from ..routes.document_design import _render_html

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow(
            f"SELECT customer_id FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE id = $1",
            plan_id
        )
        if not plan:
            raise HTTPException(404, "ISO plan not found")

        iso_row = await conn.fetchrow(f"""
            SELECT iso.code
            FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
            JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = p.iso_standard_id
            WHERE p.id = $1
        """, plan_id)
        iso_code = iso_row["code"] if iso_row else "ISO"

        docs = await conn.fetch(
            f"SELECT id, document_name, content FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE plan_id = $1 ORDER BY document_name",
            plan_id
        )
        if not docs:
            raise HTTPException(404, "No documents found for this plan")

        # Filled placeholder values for this customer
        ph_rows = await conn.fetch(f"""
            SELECT cp.placeholder_key, pd.field_value
            FROM {settings.DATABASE_APP_SCHEMA}.customer_placeholders cp
            JOIN {settings.DATABASE_APP_SCHEMA}.customer_profile_data pd ON pd.id = cp.profile_data_id
            WHERE cp.customer_id = $1 AND cp.plan_id = $2 AND pd.field_value IS NOT NULL
        """, plan["customer_id"], plan_id)
        values = {r["placeholder_key"]: r["field_value"] for r in ph_rows}

        design = await conn.fetchrow(
            f"SELECT config, direction FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs WHERE language = $1 AND is_default = true LIMIT 1", lang
        ) or await conn.fetchrow(
            f"SELECT config, direction FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs WHERE language = 'en' AND is_default = true LIMIT 1"
        )

    cfg = design["config"] if isinstance(design["config"], dict) else _json.loads(design["config"])
    direction = design["direction"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            content = doc["content"]
            if isinstance(content, str):
                content = _json.loads(content)
            html = _render_html(doc["document_name"], content, cfg, direction, values)
            pdf = WeasyprintHTML(string=html).write_pdf()
            safe_name = (doc["document_name"] or str(doc["id"])).replace("/", "-").replace("\\", "-").strip()
            zf.writestr(f"{safe_name}.pdf", pdf)

    zip_name = iso_code.replace(" ", "_").replace("/", "-")
    encoded = quote(f"{zip_name}.zip")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}.zip"; filename*=UTF-8\'\'{encoded}'}
    )


@router.get("/{plan_id}/templates")
async def list_plan_templates(
    plan_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    List ALL approved templates for this plan's ISO standard.
    Each entry has has_document=True/False indicating whether a customer
    document already exists for it in this plan.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            plan = await conn.fetchrow(
                f"SELECT iso_standard_id FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE id = $1",
                plan_id
            )
            if not plan:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            rows = await conn.fetch(f"""
                SELECT t.id, t.name, t.document_type, t.version_number,
                       d.id AS document_id
                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping tim ON tim.template_id = t.id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents d
                       ON d.template_id = t.id AND d.plan_id = $1
                WHERE tim.iso_standard_id = $2 AND t.status = 'approved'
                ORDER BY t.name
            """, plan_id, plan["iso_standard_id"])

            return [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "document_type": r["document_type"],
                    "version_number": r["version_number"],
                    "document_id": str(r["document_id"]) if r["document_id"] else None,
                    "has_document": r["document_id"] is not None,
                }
                for r in rows
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing templates for plan {plan_id}: {e}")
        raise HTTPException(500, str(e))


@router.post("/{plan_id}/templates/{template_id}", status_code=201)
async def add_template_to_plan(
    plan_id: UUID,
    template_id: UUID,
    current_user: dict = Depends(require_admin)
):
    """
    Add a template to an existing plan.
    Creates the customer document, seeds placeholders, and reconciles tasks.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            plan = await conn.fetchrow(f"""
                SELECT p.customer_id, p.iso_standard_id,
                       c.name AS customer_name, iso.code AS iso_code
                FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
                JOIN {settings.DATABASE_APP_SCHEMA}.customers c ON c.id = p.customer_id
                JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = p.iso_standard_id
                WHERE p.id = $1
            """, plan_id)
            if not plan:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            # Check not already added
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_documents "
                f"WHERE plan_id = $1 AND template_id = $2",
                plan_id, template_id
            )
            if existing:
                raise HTTPException(400, "Template already added to this plan")

            template = await conn.fetchrow(
                f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1 AND status = 'approved'",
                template_id
            )
            if not template:
                raise HTTPException(404, f"Template {template_id} not found or not approved")

            document_id = await create_customer_document(
                conn=conn,
                customer_id=plan["customer_id"],
                plan_id=plan_id,
                template=dict(template),
                customer_name=plan["customer_name"],
                iso_code=plan["iso_code"],
            )

            await seed_placeholders(conn, plan["customer_id"], plan_id, dict(template))
            sync = await reconcile_plan(conn, plan["customer_id"], plan_id)

            logger.info(
                f"Added template {template_id} to plan {plan_id}: "
                f"document={document_id} tasks_created={sync['tasks_created']}"
            )
            return {"added": True, "document_id": str(document_id), **sync}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding template {template_id} to plan {plan_id}: {e}")
        raise HTTPException(500, str(e))


@router.delete("/{plan_id}/templates/{template_id}")
async def remove_template_from_plan(
    plan_id: UUID,
    template_id: UUID,
    current_user: dict = Depends(require_admin)
):
    """
    Remove a template from a plan by deleting its customer document,
    then reconciling tasks (cancels any tasks whose key is now orphaned).
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            plan = await conn.fetchrow(
                f"SELECT customer_id FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE id = $1",
                plan_id
            )
            if not plan:
                raise HTTPException(404, f"ISO plan {plan_id} not found")

            doc = await conn.fetchrow(
                f"SELECT id, document_name FROM {settings.DATABASE_APP_SCHEMA}.customer_documents "
                f"WHERE plan_id = $1 AND template_id = $2",
                plan_id, template_id
            )
            if not doc:
                raise HTTPException(404, "Template not found in this plan")

            await conn.execute(
                f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE id = $1",
                doc["id"]
            )

            sync = await reconcile_plan(conn, plan["customer_id"], plan_id)

            logger.info(
                f"Removed template {template_id} from plan {plan_id}: "
                f"document={doc['id']} tasks_cancelled={sync['cancelled']}"
            )
            return {
                "removed": True,
                "document_name": doc["document_name"],
                "tasks_cancelled": sync["cancelled"],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing template {template_id} from plan {plan_id}: {e}")
        raise HTTPException(500, str(e))
