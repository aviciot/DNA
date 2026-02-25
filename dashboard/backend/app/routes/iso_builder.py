"""
ISO Builder AI Endpoint
========================
Accepts a PDF upload, creates an ai_task, pushes to iso:build Redis stream.
"""

import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from ..database import get_db_pool
from ..config import settings
from ..auth import get_current_user, require_admin
from ..redis_client import get_redis

router = APIRouter(prefix="/api/v1/iso-builder", tags=["ISO Builder"])
logger = logging.getLogger(__name__)

PDF_UPLOAD_DIR = os.getenv("ISO_PDF_STORAGE_PATH", "/app/storage/iso_pdfs")
os.makedirs(PDF_UPLOAD_DIR, exist_ok=True)


@router.post("/start")
async def start_iso_build(
    iso_code: str = Form(..., description="ISO code, e.g. ISO 27001:2022"),
    iso_name: str = Form(..., description="Full ISO standard name"),
    iso_description: str = Form("", description="Optional description"),
    iso_color: str = Form("#8b5cf6", description="Hex color for UI"),
    iso_language: str = Form("en", description="Language code for generated content (e.g. en, he, fr)"),
    template_format: str = Form("legacy", description="Template format: legacy or formal"),
    pdf_file: UploadFile = File(..., description="ISO standard PDF"),
    current_user: dict = Depends(require_admin),
):
    """
    Upload an ISO PDF and kick off AI-powered ISO standard + template generation.

    1. Saves PDF to disk
    2. Creates ai_task record (type=iso_build)
    3. Pushes to iso:build Redis stream
    4. Returns task_id for WebSocket progress tracking
    """
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    # Validate file size (max 50MB)
    MAX_PDF_BYTES = 50 * 1024 * 1024
    content = await pdf_file.read()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, f"PDF too large ({len(content) // (1024*1024)}MB). Maximum is 50MB.")
    if len(content) == 0:
        raise HTTPException(400, "Uploaded PDF is empty")

    task_id = str(uuid.uuid4())
    safe_name = f"{task_id}.pdf"
    pdf_path = os.path.join(PDF_UPLOAD_DIR, safe_name)

    # Save uploaded file
    try:
        with open(pdf_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save PDF: {e}")
        raise HTTPException(500, "Failed to save uploaded file")

    pool = await get_db_pool()
    redis_client = await get_redis()

    # Resolve active provider/model from DB
    ai_provider = "gemini"
    ai_model = settings.GEMINI_MODEL if hasattr(settings, "GEMINI_MODEL") else "gemini-2.5-flash"
    try:
        async with pool.acquire() as conn:
            prow = await conn.fetchrow(
                f"SELECT value FROM {settings.DATABASE_APP_SCHEMA}.ai_settings WHERE key = 'active_provider'"
            )
            mrow = await conn.fetchrow(
                f"SELECT value FROM {settings.DATABASE_APP_SCHEMA}.ai_settings WHERE key = 'active_model'"
            )
        if prow:
            ai_provider = prow["value"]
        if mrow:
            ai_model = mrow["value"]
    except Exception as e:
        logger.warning(f"Could not read ai_settings, using defaults: {e}")

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_tasks (
                    id, task_type, status, created_by, created_at
                ) VALUES ($1, 'iso_build', 'pending', $2, $3)
                """,
                uuid.UUID(task_id),
                current_user["user_id"],
                datetime.utcnow(),
            )

        await redis_client.add_to_stream(
            "iso:build",
            {
                "task_id": task_id,
                "file_path": pdf_path,
                "iso_code": iso_code,
                "iso_name": iso_name,
                "iso_description": iso_description,
                "iso_color": iso_color,
                "iso_language": iso_language,
                "template_format": template_format,
                "created_by": str(current_user["user_id"]),
                "trace_id": str(uuid.uuid4()),
                "ai_provider": ai_provider,
                "ai_model": ai_model,
            },
        )

        logger.info(f"ISO build task {task_id} queued for {iso_code}")

        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"ISO build started for {iso_code}. Track progress via /ws/tasks/{task_id}",
        }

    except Exception as e:
        # Clean up saved file on failure
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        logger.error(f"Failed to queue ISO build task: {e}")
        raise HTTPException(500, f"Failed to start ISO build: {str(e)}")


@router.get("/tasks/{task_id}/status")
async def get_iso_build_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get status of an ISO build task."""
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT id, status, progress, current_step, result, error,
                       iso_standard_id, created_at, completed_at
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE id = $1 AND task_type = 'iso_build'
                """,
                uuid.UUID(task_id),
            )

        if not row:
            raise HTTPException(404, "ISO build task not found")

        return {
            "task_id": str(row["id"]),
            "status": row["status"],
            "progress": row["progress"],
            "current_step": row["current_step"],
            "iso_standard_id": str(row["iso_standard_id"]) if row["iso_standard_id"] else None,
            "result": row["result"],
            "error": row["error"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ISO build status: {e}")
        raise HTTPException(500, str(e))
