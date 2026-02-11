"""
DNA Backend - Template Preview API Routes
==========================================
API endpoints for template preview proof of concept.

Part of Phase 1: Template Preview System
"""

import os
import uuid
import logging
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services.simple_placeholder_parser import extract_placeholders_from_docx
from ..services.simple_document_generator import generate_filled_document
from ..auth import get_current_user

router = APIRouter(prefix="/api/v1/template-preview", tags=["Template Preview"])
logger = logging.getLogger(__name__)

# Storage paths
TEMPLATE_STORAGE = os.getenv("TEMPLATE_STORAGE_PATH", "/app/storage/templates")
OUTPUT_STORAGE = os.getenv("OUTPUT_STORAGE_PATH", "/app/storage/outputs")

# Ensure directories exist
os.makedirs(TEMPLATE_STORAGE, exist_ok=True)
os.makedirs(OUTPUT_STORAGE, exist_ok=True)


# =============================================================================
# Pydantic Models
# =============================================================================

class GeneratePreviewRequest(BaseModel):
    """Request model for generating preview."""
    template_id: str
    filled_data: Dict[str, Any]


class UploadResponse(BaseModel):
    """Response model for template upload."""
    template_id: str
    filename: str
    total_placeholders: int
    fields: list


class PreviewResponse(BaseModel):
    """Response model for preview generation."""
    preview_id: str
    pdf_url: str
    docx_url: str
    success: bool
    error: str = None


# =============================================================================
# Routes
# =============================================================================

@router.post("/upload-template", response_model=UploadResponse)
async def upload_template(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    Upload template DOCX and extract placeholders.

    Args:
        file: DOCX file to upload

    Returns:
        Template ID and list of detected fields
    """
    try:
        # Validate file type
        if not file.filename.endswith('.docx'):
            raise HTTPException(
                status_code=400,
                detail="Only .docx files are supported"
            )

        # Generate unique template ID
        template_id = str(uuid.uuid4())

        # Save uploaded file
        template_path = os.path.join(TEMPLATE_STORAGE, f"{template_id}.docx")
        with open(template_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"Saved template: {template_path}")

        # Parse template to extract placeholders
        result = extract_placeholders_from_docx(template_path)

        return UploadResponse(
            template_id=template_id,
            filename=file.filename,
            total_placeholders=result["total_placeholders"],
            fields=result["fields"]
        )

    except Exception as e:
        logger.error(f"Error uploading template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-preview", response_model=PreviewResponse)
async def generate_preview(
    request: GeneratePreviewRequest,
    current_user = Depends(get_current_user)
):
    """
    Generate preview document from template with filled data.

    Args:
        request: Template ID and filled data

    Returns:
        Preview ID and URLs to download DOCX/PDF
    """
    try:
        # Validate template exists
        template_path = os.path.join(TEMPLATE_STORAGE, f"{request.template_id}.docx")
        if not os.path.exists(template_path):
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {request.template_id}"
            )

        # Generate unique preview ID
        preview_id = str(uuid.uuid4())

        # Create output directory for this preview
        output_dir = os.path.join(OUTPUT_STORAGE, preview_id)

        # Generate filled document
        result = generate_filled_document(
            template_path=template_path,
            filled_data=request.filled_data,
            output_dir=output_dir,
            output_filename="preview"
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Document generation failed: {result['error']}"
            )

        # Return URLs to download files
        return PreviewResponse(
            preview_id=preview_id,
            pdf_url=f"/api/v1/template-preview/download/{preview_id}/pdf",
            docx_url=f"/api/v1/template-preview/download/{preview_id}/docx",
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{preview_id}/{format}")
async def download_preview(
    preview_id: str,
    format: str,
    current_user = Depends(get_current_user)
):
    """
    Download generated preview file.

    Args:
        preview_id: Preview ID from generate-preview
        format: 'pdf' or 'docx'

    Returns:
        File stream
    """
    try:
        # Validate format
        if format not in ['pdf', 'docx']:
            raise HTTPException(
                status_code=400,
                detail="Format must be 'pdf' or 'docx'"
            )

        # Build file path
        file_path = os.path.join(
            OUTPUT_STORAGE,
            preview_id,
            f"preview.{format}"
        )

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"Preview file not found: {preview_id}"
            )

        # Determine media type
        media_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Return file
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=f"preview.{format}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates(current_user = Depends(get_current_user)):
    """
    List all uploaded templates.

    Returns:
        List of templates with IDs and metadata
    """
    try:
        templates = []

        for filename in os.listdir(TEMPLATE_STORAGE):
            if filename.endswith('.docx'):
                template_id = filename.replace('.docx', '')
                template_path = os.path.join(TEMPLATE_STORAGE, filename)

                # Get file stats
                stat = os.stat(template_path)

                templates.append({
                    "template_id": template_id,
                    "uploaded_at": stat.st_ctime,
                    "size_bytes": stat.st_size
                })

        return {"templates": templates}

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user = Depends(get_current_user)
):
    """
    Delete a template.

    Args:
        template_id: Template ID to delete

    Returns:
        Success message
    """
    try:
        template_path = os.path.join(TEMPLATE_STORAGE, f"{template_id}.docx")

        if not os.path.exists(template_path):
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {template_id}"
            )

        os.remove(template_path)
        logger.info(f"Deleted template: {template_id}")

        return {"message": "Template deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint (no auth required for testing).

    Returns:
        Service status
    """
    return {
        "status": "healthy",
        "service": "template-preview",
        "template_storage": TEMPLATE_STORAGE,
        "output_storage": OUTPUT_STORAGE,
        "storage_exists": os.path.exists(TEMPLATE_STORAGE) and os.path.exists(OUTPUT_STORAGE)
    }
