"""
Interview Session API
=====================
Endpoints for the DNA user interview flow.
Questions ordered by document. Each question includes related doc fill %.
Answers tracked with source channel + collected_by user.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from ..database import get_db_pool
from ..auth import get_current_user
from ..services.placeholder_service import apply_profile_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/customers/{customer_id}/interview", tags=["Interview"])

# Valid answer channels
VALID_CHANNELS = {"manual", "ai_chat", "email", "self_service", "automation", "import"}


class DocumentProgress(BaseModel):
    document_id: Optional[str] = None
    template_name: str
    completion_percentage: int


class PlaceholderQuestion(BaseModel):
    placeholder_key: str
    display_label: str
    data_type: str
    is_required: bool
    status: str
    allowed_channels: List[str]
    template_count: int
    template_names: List[str]
    document_progress: List[DocumentProgress]  # fill % per related doc


class InterviewSession(BaseModel):
    customer_id: int
    customer_name: str
    total_pending: int
    total_collected: int
    questions: List[PlaceholderQuestion]


class AnswerSubmit(BaseModel):
    placeholder_key: str
    answer: str
    source: str = "manual"


@router.get("", response_model=InterviewSession)
async def get_interview_session(
    customer_id: int,
    plan_id: Optional[UUID] = None,
    user: dict = Depends(get_current_user)
):
    """
    Returns all placeholders for a customer ordered by document then required-first.
    Each question includes which documents use it and their current fill %.
    """
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        customer = await conn.fetchrow(
            "SELECT id, name FROM dna_app.customers WHERE id = $1", customer_id
        )
        if not customer:
            raise HTTPException(404, "Customer not found")

        plan_filter = "AND cp.plan_id = $2" if plan_id else ""
        params = [customer_id, plan_id] if plan_id else [customer_id]

        rows = await conn.fetch(f"""
            SELECT
                cp.placeholder_key,
                cp.display_label,
                cp.data_type,
                cp.is_required,
                cp.status,
                cp.template_ids,
                cp.allowed_channels,
                array_agg(DISTINCT t.name) FILTER (WHERE t.name IS NOT NULL) AS template_names,
                -- Order by first template name for document grouping
                MIN(t.name) AS first_template_name
            FROM dna_app.customer_placeholders cp
            LEFT JOIN LATERAL unnest(cp.template_ids) AS tid(id) ON true
            LEFT JOIN dna_app.templates t ON t.id = tid.id
            WHERE cp.customer_id = $1 {plan_filter}
            GROUP BY cp.placeholder_key, cp.display_label, cp.data_type,
                     cp.is_required, cp.status, cp.template_ids, cp.allowed_channels
            ORDER BY
                MIN(t.name) NULLS LAST,   -- group by document
                cp.is_required DESC,       -- required first within doc
                cp.status ASC              -- pending before collected
        """, *params)

        # Fetch document fill % for all templates in one query
        doc_rows = await conn.fetch("""
            SELECT cd.id, cd.template_id, cd.template_name, cd.completion_percentage
            FROM dna_app.customer_documents cd
            WHERE cd.customer_id = $1
        """, customer_id)
        doc_by_template = {str(r['template_id']): r for r in doc_rows}

        questions = []
        for row in rows:
            template_ids = row['template_ids'] or []
            template_names = row['template_names'] or []
            allowed = row['allowed_channels'] or ['manual', 'ai_chat', 'email', 'self_service', 'automation']

            # Build doc progress for each related template
            doc_progress = []
            for tid in template_ids:
                doc = doc_by_template.get(str(tid))
                doc_progress.append(DocumentProgress(
                    document_id=str(doc['id']) if doc else None,
                    template_name=doc['template_name'] if doc else str(tid),
                    completion_percentage=doc['completion_percentage'] if doc else 0,
                ))

            questions.append(PlaceholderQuestion(
                placeholder_key=row['placeholder_key'],
                display_label=row['display_label'],
                data_type=row['data_type'],
                is_required=row['is_required'],
                status=row['status'],
                allowed_channels=allowed,
                template_count=len(template_ids),
                template_names=template_names,
                document_progress=doc_progress,
            ))

        pending = sum(1 for q in questions if q.status == 'pending')
        collected = sum(1 for q in questions if q.status == 'collected')

        return InterviewSession(
            customer_id=customer_id,
            customer_name=customer['name'],
            total_pending=pending,
            total_collected=collected,
            questions=questions
        )


@router.post("/answer")
async def submit_answer(
    customer_id: int,
    body: AnswerSubmit,
    user: dict = Depends(get_current_user)
):
    """
    Submit a text answer for a placeholder.
    Saves to profile_data (with collected_by + source), updates all placeholders + tasks + documents.
    """
    if body.source not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid source. Must be one of: {', '.join(VALID_CHANNELS)}")

    pool = await get_db_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await apply_profile_answer(
                conn=conn,
                customer_id=customer_id,
                field_key=body.placeholder_key,
                field_value=body.answer,
                source=body.source,
                updated_by=user.get('user_id'),
            )

    logger.info(
        f"Answer saved: customer={customer_id} key={body.placeholder_key} "
        f"source={body.source} by={user.get('user_id')}"
    )

    return {
        "placeholder_key": body.placeholder_key,
        "source": body.source,
        "placeholders_updated": result['placeholders_updated'],
        "tasks_completed": result['tasks_completed'],
        "docs_updated": result['docs_updated'],
    }


@router.post("/answer-file")
async def submit_file_answer(
    customer_id: int,
    placeholder_key: str = Form(...),
    source: str = Form("manual"),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    Submit a file answer (logo, certificate, org chart, etc.).
    """
    import os, uuid as _uuid

    if source not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid source. Must be one of: {', '.join(VALID_CHANNELS)}")

    pool = await get_db_pool()

    upload_dir = f"/app/uploads/customers/{customer_id}"
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{_uuid.uuid4()}_{file.filename}"
    file_path = f"{upload_dir}/{filename}"

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await apply_profile_answer(
                conn=conn,
                customer_id=customer_id,
                field_key=placeholder_key,
                field_value=file.filename,
                file_path=file_path,
                file_mime_type=file.content_type,
                data_type='file',
                source=source,
                updated_by=user.get('user_id'),
            )

    logger.info(
        f"File answer saved: customer={customer_id} key={placeholder_key} "
        f"file={file.filename} source={source} by={user.get('user_id')}"
    )

    return {
        "placeholder_key": placeholder_key,
        "file_path": file_path,
        "source": source,
        "placeholders_updated": result['placeholders_updated'],
        "tasks_completed": result['tasks_completed'],
        "docs_updated": result['docs_updated'],
    }


@router.patch("/placeholder/{placeholder_key}/channels")
async def update_allowed_channels(
    customer_id: int,
    placeholder_key: str,
    channels: List[str],
    plan_id: Optional[UUID] = None,
    user: dict = Depends(get_current_user)
):
    """
    Update which channels are allowed to answer a specific placeholder.
    """
    invalid = set(channels) - VALID_CHANNELS
    if invalid:
        raise HTTPException(400, f"Invalid channels: {invalid}. Valid: {VALID_CHANNELS}")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        plan_filter = "AND plan_id = $4" if plan_id else ""
        params = [channels, customer_id, placeholder_key]
        if plan_id:
            params.append(plan_id)

        updated = await conn.fetchval(f"""
            UPDATE dna_app.customer_placeholders
            SET allowed_channels = $1
            WHERE customer_id = $2 AND placeholder_key = $3 {plan_filter}
            RETURNING id
        """, *params)

        if not updated:
            raise HTTPException(404, "Placeholder not found")

    return {"placeholder_key": placeholder_key, "allowed_channels": channels}
