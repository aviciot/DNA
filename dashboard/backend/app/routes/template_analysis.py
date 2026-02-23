"""
DNA Backend - Template Analysis & Approval API Routes
======================================================
API endpoints for AI-assisted template creation and approval workflow.

Workflow:
1. Upload reference document
2. AI analyzes and suggests placeholders
3. Admin reviews/edits suggestions
4. Apply recommendations to create template
5. Preview template
6. Approve for use
"""

import os
import uuid
import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime

from ..database import get_db_pool
from ..config import settings
from ..auth import get_current_user
from ..redis_client import get_redis
from ..services.placeholder_injector import inject_placeholders

router = APIRouter(prefix="/api/v1/template-analysis", tags=["Template Analysis"])
logger = logging.getLogger(__name__)

# Storage paths
TEMPLATE_STORAGE = os.getenv("TEMPLATE_STORAGE_PATH", "/app/storage/templates")
REFERENCE_STORAGE = os.getenv("REFERENCE_STORAGE_PATH", "/app/storage/references")

os.makedirs(TEMPLATE_STORAGE, exist_ok=True)
os.makedirs(REFERENCE_STORAGE, exist_ok=True)


# =============================================================================
# Pydantic Models
# =============================================================================

class ReplacementSuggestion(BaseModel):
    """Single replacement suggestion from AI."""
    original_text: str
    placeholder: str
    question: str
    question_context: str
    field_type: str = "text"
    confidence: float = 0.8  # AI confidence this needs customization (0.0-1.0)
    is_mandatory: bool = True  # Whether this field is required
    semantic_tags: list[str] = []  # Tags for categorization and search
    priority: str = "medium"  # Priority: high, medium, low
    requires_evidence: bool = False  # Whether customer needs to provide documentation
    evidence_description: str = ""  # Description of what evidence is needed


class AnalysisRequest(BaseModel):
    """Request to analyze a template file."""
    template_file_id: str = Field(..., description="UUID of uploaded reference document")


class AnalysisResponse(BaseModel):
    """Response from analysis request."""
    task_id: str
    status: str
    message: str


class RecommendationsResponse(BaseModel):
    """AI recommendations for a template."""
    template_file_id: str
    replacements: List[ReplacementSuggestion]
    status: str  # pending, approved, applied
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UpdateRecommendationsRequest(BaseModel):
    """Request to update AI recommendations."""
    replacements: List[ReplacementSuggestion]


class ApplyRecommendationsRequest(BaseModel):
    """Request to apply recommendations and create template."""
    template_name: str
    template_description: Optional[str] = None


class ApplyResponse(BaseModel):
    """Response after applying recommendations."""
    success: bool
    template_id: Optional[str] = None
    template_file_path: Optional[str] = None
    replacements_made: int
    error: Optional[str] = None


class ApproveRequest(BaseModel):
    """Request to approve template."""
    approved: bool
    notes: Optional[str] = None


class UpdatePlaceholderTagsRequest(BaseModel):
    """Request to update tags for a specific placeholder."""
    placeholder_id: str  # The placeholder text (e.g., "{{ciso_name}}")
    semantic_tags: List[str]  # New tags list


class SuggestTagsRequest(BaseModel):
    """Request to get LLM suggestions for additional tags."""
    placeholder_id: str  # The placeholder to suggest tags for
    additional_context: Optional[str] = None  # Optional extra context


# =============================================================================
# Routes
# =============================================================================

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_template(
    request: AnalysisRequest,
    current_user=Depends(get_current_user)
):
    """
    Trigger AI analysis of a reference document.

    Args:
        request: Contains template_file_id

    Returns:
        Task ID for tracking analysis progress
    """
    try:
        pool = await get_db_pool()
        redis_client = await get_redis()

        # Get template file info
        async with pool.acquire() as conn:
            file_row = await conn.fetchrow(
                f"""
                SELECT id, filename, file_path, mime_type
                FROM {settings.DATABASE_APP_SCHEMA}.template_files
                WHERE id = $1
                """,
                uuid.UUID(request.template_file_id)
            )

            if not file_row:
                raise HTTPException(status_code=404, detail="Template file not found")

        # Create AI task
        task_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_tasks (
                    id, template_file_id, task_type, status,
                    created_by, created_at
                )
                VALUES ($1, $2, 'analyze', 'pending', $3, $4)
                """,
                uuid.UUID(task_id),
                uuid.UUID(request.template_file_id),
                current_user["user_id"],  # Integer, not UUID
                datetime.utcnow()
            )

        # Publish to Redis stream
        await redis_client.add_to_stream(
            "template:analyze",
            {
                "task_id": task_id,
                "template_file_id": request.template_file_id,
                "file_path": file_row["file_path"],
                "created_by": str(current_user["user_id"]),
                "trace_id": str(uuid.uuid4())
            }
        )

        logger.info(f"Analysis task created: {task_id} for file {request.template_file_id}")

        return AnalysisResponse(
            task_id=task_id,
            status="pending",
            message="Analysis task pending. Check task status for results."
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error creating analysis task: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_file_id}/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    template_file_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get AI recommendations for a template.

    Args:
        template_file_id: UUID of template file

    Returns:
        AI-suggested replacements and questions
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Find most recent completed analysis task
            task_row = await conn.fetchrow(
                f"""
                SELECT id, result, status, created_at, completed_at
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE template_file_id = $1
                AND task_type = 'analyze'
                AND status = 'completed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                uuid.UUID(template_file_id)
            )

            if not task_row:
                raise HTTPException(
                    status_code=404,
                    detail="No analysis results found. Please run analysis first."
                )

            result_data = task_row["result"]
            # Parse JSON if needed (JSONB column might return string)
            if isinstance(result_data, str):
                result_data = json.loads(result_data)
            replacements = result_data.get("replacements", [])

            return RecommendationsResponse(
                template_file_id=template_file_id,
                replacements=[ReplacementSuggestion(**r) for r in replacements],
                status="pending",
                created_at=task_row["created_at"].isoformat() if task_row["created_at"] else None,
                updated_at=task_row["completed_at"].isoformat() if task_row["completed_at"] else None
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_file_id}/recommendations")
async def update_recommendations(
    template_file_id: str,
    request: UpdateRecommendationsRequest,
    current_user=Depends(get_current_user)
):
    """
    Update AI recommendations (admin can edit before applying).

    Args:
        template_file_id: UUID of template file
        request: Updated replacements list

    Returns:
        Success message
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Update the most recent analysis task result
            await conn.execute(
                f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.ai_tasks
                SET result = $1
                WHERE template_file_id = $2
                AND task_type = 'analyze'
                AND id = (
                    SELECT id FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                    WHERE template_file_id = $2 AND task_type = 'analyze'
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                json.dumps({
                    "replacements": [r.model_dump() for r in request.replacements]
                }),
                uuid.UUID(template_file_id)
            )

        logger.info(f"Updated recommendations for template {template_file_id}")

        return {"message": "Recommendations updated successfully"}

    except Exception as e:
        logger.error(f"Error updating recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{template_file_id}/recommendations/tags")
async def update_placeholder_tags(
    template_file_id: str,
    request: UpdatePlaceholderTagsRequest,
    current_user=Depends(get_current_user)
):
    """
    Update semantic tags for a specific placeholder.

    Args:
        template_file_id: UUID of template file
        request: Placeholder ID and new tags

    Returns:
        Success message with updated placeholder
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Get current recommendations
            task_row = await conn.fetchrow(
                f"""
                SELECT result
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE template_file_id = $1
                AND task_type = 'analyze'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                uuid.UUID(template_file_id)
            )

            if not task_row or not task_row["result"]:
                raise HTTPException(status_code=404, detail="No recommendations found")

            # Parse result
            result_data = task_row["result"]
            if isinstance(result_data, str):
                result_data = json.loads(result_data)

            replacements = result_data.get("replacements", [])

            # Find and update the specific placeholder
            updated = False
            for replacement in replacements:
                if replacement.get("placeholder") == request.placeholder_id:
                    replacement["semantic_tags"] = request.semantic_tags
                    updated = True
                    logger.info(f"Updated tags for {request.placeholder_id}: {request.semantic_tags}")
                    break

            if not updated:
                raise HTTPException(
                    status_code=404,
                    detail=f"Placeholder '{request.placeholder_id}' not found"
                )

            # Save back to database
            await conn.execute(
                f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.ai_tasks
                SET result = $1
                WHERE template_file_id = $2
                AND task_type = 'analyze'
                AND id = (
                    SELECT id FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                    WHERE template_file_id = $2 AND task_type = 'analyze'
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                json.dumps({"replacements": replacements}),
                uuid.UUID(template_file_id)
            )

        return {
            "message": "Tags updated successfully",
            "placeholder": request.placeholder_id,
            "tags": request.semantic_tags
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating placeholder tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_file_id}/recommendations/tags/from-template")
async def get_template_contextual_tags(
    template_file_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get contextual tags from OTHER placeholders in THIS template.
    Shows what the LLM used for related placeholders in the same document.
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            task_row = await conn.fetchrow(
                f"""
                SELECT result
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE template_file_id = $1
                AND task_type = 'analyze'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                uuid.UUID(template_file_id)
            )

            if not task_row or not task_row["result"]:
                raise HTTPException(status_code=404, detail="No analysis found")

            result_data = task_row["result"]
            if isinstance(result_data, str):
                result_data = json.loads(result_data)

            # Collect all unique tags from all placeholders
            tag_frequency = {}
            placeholder_examples = {}  # Store example placeholder for each tag

            for replacement in result_data.get("replacements", []):
                placeholder_id = replacement.get("placeholder", "")
                for tag in replacement.get("semantic_tags", []):
                    tag_frequency[tag] = tag_frequency.get(tag, 0) + 1
                    if tag not in placeholder_examples:
                        placeholder_examples[tag] = placeholder_id

            # Sort by frequency (most common first)
            sorted_tags = sorted(
                tag_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )

            logger.info(f"Template {template_file_id}: Found {len(sorted_tags)} unique tags from {len(result_data.get('replacements', []))} placeholders")
            logger.info(f"Tag frequency: {dict(sorted_tags)}")

            return {
                "tags": [
                    {
                        "tag": tag,
                        "count": count,
                        "example_placeholder": placeholder_examples[tag]
                    }
                    for tag, count in sorted_tags
                ],
                "total_tags": len(sorted_tags),
                "total_placeholders": len(result_data.get("replacements", [])),
                "source": "Same document - tags used by AI for other placeholders"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template contextual tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tags/history/{placeholder_text}")
async def get_historical_tags(
    placeholder_text: str,
    current_user=Depends(get_current_user)
):
    """
    Get historically used tags for similar placeholders across ALL templates.
    Smart suggestions based on what AI used for similar placeholders in the past.

    Args:
        placeholder_text: The placeholder to search for (e.g., "ciso_name" or "{{ciso_name}}")
    """
    try:
        pool = await get_db_pool()

        # Clean placeholder text (remove {{ }})
        clean_text = placeholder_text.strip("{}")

        logger.info(f"Searching historical tags for placeholder: {clean_text}")

        async with pool.acquire() as conn:
            # Get all completed analysis tasks
            rows = await conn.fetch(
                f"""
                SELECT result, template_file_id, created_at
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE task_type = 'analyze'
                AND status = 'completed'
                AND result IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 500
                """
            )

            # Analyze all placeholders to find similar ones
            similar_placeholders = []
            exact_matches = []
            tag_frequency = {}

            for row in rows:
                result = row["result"]
                if isinstance(result, str):
                    result = json.loads(result)

                for replacement in result.get("replacements", []):
                    placeholder = replacement.get("placeholder", "").strip("{}")
                    tags = replacement.get("semantic_tags", [])

                    # Exact match (same placeholder name)
                    if placeholder.lower() == clean_text.lower():
                        exact_matches.append({
                            "placeholder": replacement.get("placeholder"),
                            "original_text": replacement.get("original_text"),
                            "tags": tags,
                            "template_file_id": str(row["template_file_id"])
                        })
                        # Count tag frequency for exact matches
                        for tag in tags:
                            tag_frequency[tag] = tag_frequency.get(tag, 0) + 1

                    # Fuzzy match (similar placeholder names)
                    elif (
                        clean_text.lower() in placeholder.lower() or
                        placeholder.lower() in clean_text.lower() or
                        # Check if they share significant words
                        any(word in placeholder.lower() for word in clean_text.lower().split('_') if len(word) > 3)
                    ):
                        similar_placeholders.append({
                            "placeholder": replacement.get("placeholder"),
                            "original_text": replacement.get("original_text"),
                            "tags": tags,
                            "similarity": "partial"
                        })

            # Sort tags by frequency
            sorted_tags = sorted(
                tag_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )

            # Calculate tag statistics
            total_exact_matches = len(exact_matches)
            suggested_tags = []

            for tag, count in sorted_tags:
                percentage = (count / total_exact_matches * 100) if total_exact_matches > 0 else 0
                suggested_tags.append({
                    "tag": tag,
                    "count": count,
                    "percentage": round(percentage, 1),
                    "confidence": "high" if percentage > 70 else "medium" if percentage > 40 else "low"
                })

            logger.info(f"Found {total_exact_matches} exact matches and {len(similar_placeholders)} similar placeholders")
            logger.info(f"Top tags: {[t['tag'] for t in suggested_tags[:5]]}")

            return {
                "placeholder": clean_text,
                "exact_matches_count": total_exact_matches,
                "similar_matches_count": len(similar_placeholders),
                "suggested_tags": suggested_tags[:10],  # Top 10
                "exact_match_examples": exact_matches[:3],  # Show 3 examples
                "similar_match_examples": similar_placeholders[:3],  # Show 3 examples
                "source": "Historical data - tags used for similar placeholders across all templates"
            }

    except Exception as e:
        logger.error(f"Error getting historical tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_file_id}/apply", response_model=ApplyResponse)
async def apply_recommendations(
    template_file_id: str,
    request: ApplyRecommendationsRequest,
    current_user=Depends(get_current_user)
):
    """
    Apply AI recommendations to create template with placeholders.

    Args:
        template_file_id: UUID of reference document
        request: Template name and description

    Returns:
        Created template info
    """
    try:
        pool = await get_db_pool()

        # Get template file and recommendations
        async with pool.acquire() as conn:
            file_row = await conn.fetchrow(
                f"""
                SELECT id, filename, file_path
                FROM {settings.DATABASE_APP_SCHEMA}.template_files
                WHERE id = $1
                """,
                uuid.UUID(template_file_id)
            )

            if not file_row:
                raise HTTPException(status_code=404, detail="Template file not found")

            # Get latest recommendations
            task_row = await conn.fetchrow(
                f"""
                SELECT result
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE template_file_id = $1
                AND task_type = 'analyze'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                uuid.UUID(template_file_id)
            )

            if not task_row or not task_row["result"]:
                raise HTTPException(
                    status_code=404,
                    detail="No recommendations found. Please analyze first."
                )

        # Build replacement map
        result_data = task_row["result"]
        # Parse JSON if needed (JSONB column might return string)
        if isinstance(result_data, str):
            result_data = json.loads(result_data)
        replacements = result_data.get("replacements", [])
        replacement_map = {
            r["original_text"]: r["placeholder"]
            for r in replacements
        }

        # Generate template with placeholders
        template_id = str(uuid.uuid4())
        template_path = os.path.join(TEMPLATE_STORAGE, f"{template_id}.docx")

        result = inject_placeholders(
            source_path=file_row["file_path"],
            output_path=template_path,
            replacement_map=replacement_map
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create template: {result['error']}"
            )

        # Save template to database
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.templates (
                    id, name, description, template_file_id,
                    template_structure, status, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, 'draft', $6, $7)
                """,
                uuid.UUID(template_id),
                request.template_name,
                request.template_description,
                uuid.UUID(template_file_id),
                json.dumps({
                    "document_title": request.template_name,
                    "fixed_sections": [],  # No fixed sections for AI-generated templates
                    "fillable_sections": [
                        {
                            "id": r["placeholder"].strip("{}"),
                            "title": r["question"],
                            "location": r.get("original_text", "")[:50],  # First 50 chars of original text
                            "type": r.get("field_type", "text"),
                            "semantic_tags": r.get("semantic_tags", []),
                            "current_content": None,
                            "format": None,
                            "placeholder": r["placeholder"],
                            "is_mandatory": r.get("is_mandatory", True),
                            "mandatory_confidence": r.get("confidence", 0.8),
                            "priority": r.get("priority", "medium"),
                            "requires_evidence": r.get("requires_evidence", False),
                            "evidence_description": r.get("evidence_description", "")
                        }
                        for r in replacements
                    ],
                    "metadata": {
                        "source_file": file_row["filename"],
                        "parsed_at": datetime.utcnow().isoformat(),
                        "total_fixed_sections": 0,
                        "total_fillable_sections": len(replacements),
                        "semantic_tags_used": list(set([tag for r in replacements for tag in r.get("semantic_tags", [])]))
                    }
                }),
                current_user["user_id"],  # Integer, not UUID
                datetime.utcnow()
            )

        logger.info(f"Template created: {template_id} with {result['replacements_made']} placeholders")

        return ApplyResponse(
            success=True,
            template_id=template_id,
            template_file_path=template_path,
            replacements_made=result["replacements_made"],
            error=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/approve")
async def approve_template(
    template_id: str,
    request: ApproveRequest,
    current_user=Depends(get_current_user)
):
    """
    Approve or reject template.

    Args:
        template_id: UUID of template
        request: Approval decision and notes

    Returns:
        Success message
    """
    try:
        pool = await get_db_pool()

        new_status = "approved" if request.approved else "archived"

        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                SET status = $1
                WHERE id = $2
                """,
                new_status,
                uuid.UUID(template_id)
            )

        action = "approved" if request.approved else "rejected"
        logger.info(f"Template {template_id} {action} by user {current_user['user_id']}")

        return {
            "message": f"Template {action} successfully",
            "status": new_status
        }

    except Exception as e:
        logger.error(f"Error approving template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Template Management
# =============================================================================

@router.get("/templates")
async def list_all_templates(
    current_user=Depends(get_current_user)
):
    """
    Get all templates from the dna_app schema.

    Returns:
        List of all templates with basic info
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            templates = await conn.fetch(
                f"""
                SELECT t.id, t.name, t.description, t.status,
                       t.created_at, t.updated_at,
                       tf.filename as reference_document,
                       u.email as created_by_email
                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.template_files tf
                ON t.template_file_id = tf.id
                LEFT JOIN auth.users u
                ON t.created_by = u.id
                ORDER BY t.created_at DESC
                """
            )

        return [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "description": row["description"],
                "status": row["status"],
                "reference_document": row["reference_document"],
                "created_by": row["created_by_email"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            }
            for row in templates
        ]

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Phase 2: Template-ISO Association Endpoints
# =============================================================================

class AssociateISORequest(BaseModel):
    """Request to associate template with ISO standards."""
    iso_standard_ids: List[str] = Field(..., description="List of ISO standard UUIDs")


@router.post("/templates/{template_id}/iso-standards")
async def associate_template_with_iso(
    template_id: str,
    request: AssociateISORequest,
    current_user=Depends(get_current_user)
):
    """
    Associate a template with one or more ISO standards.

    Args:
        template_id: UUID of template
        request: List of ISO standard IDs

    Returns:
        Success message with associated ISO standards
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Verify template exists
            template_exists = await conn.fetchval(
                f"""
                SELECT EXISTS(
                    SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.templates
                    WHERE id = $1
                )
                """,
                uuid.UUID(template_id)
            )

            if not template_exists:
                raise HTTPException(status_code=404, detail="Template not found")

            # Verify all ISO standards exist
            for iso_id in request.iso_standard_ids:
                iso_exists = await conn.fetchval(
                    f"""
                    SELECT EXISTS(
                        SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.iso_standards
                        WHERE id = $1
                    )
                    """,
                    uuid.UUID(iso_id)
                )

                if not iso_exists:
                    raise HTTPException(
                        status_code=404,
                        detail=f"ISO standard {iso_id} not found"
                    )

            # Insert associations (ON CONFLICT DO NOTHING to handle duplicates)
            for iso_id in request.iso_standard_ids:
                await conn.execute(
                    f"""
                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_iso_standards
                    (template_id, iso_standard_id, created_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (template_id, iso_standard_id) DO NOTHING
                    """,
                    uuid.UUID(template_id),
                    uuid.UUID(iso_id),
                    datetime.utcnow()
                )

            # Get associated ISO standards details
            iso_standards = await conn.fetch(
                f"""
                SELECT iso.id, iso.code, iso.name, iso.description
                FROM {settings.DATABASE_APP_SCHEMA}.iso_standards iso
                JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_standards tis
                ON iso.id = tis.iso_standard_id
                WHERE tis.template_id = $1
                """,
                uuid.UUID(template_id)
            )

        logger.info(f"Associated template {template_id} with {len(request.iso_standard_ids)} ISO standards")

        return {
            "message": f"Successfully associated template with {len(request.iso_standard_ids)} ISO standard(s)",
            "template_id": template_id,
            "iso_standards": [
                {
                    "id": str(row["id"]),
                    "code": row["code"],
                    "name": row["name"],
                    "description": row["description"]
                }
                for row in iso_standards
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error associating template with ISO: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}/iso-standards")
async def get_template_iso_standards(
    template_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get all ISO standards associated with a template.

    Args:
        template_id: UUID of template

    Returns:
        List of associated ISO standards
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Verify template exists
            template_exists = await conn.fetchval(
                f"""
                SELECT EXISTS(
                    SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.templates
                    WHERE id = $1
                )
                """,
                uuid.UUID(template_id)
            )

            if not template_exists:
                raise HTTPException(status_code=404, detail="Template not found")

            # Get associated ISO standards
            iso_standards = await conn.fetch(
                f"""
                SELECT iso.id, iso.code, iso.name, iso.description,
                       tis.created_at as associated_at
                FROM {settings.DATABASE_APP_SCHEMA}.iso_standards iso
                JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_standards tis
                ON iso.id = tis.iso_standard_id
                WHERE tis.template_id = $1
                ORDER BY iso.code
                """,
                uuid.UUID(template_id)
            )

        return {
            "template_id": template_id,
            "iso_standards": [
                {
                    "id": str(row["id"]),
                    "code": row["code"],
                    "name": row["name"],
                    "description": row["description"],
                    "associated_at": row["associated_at"].isoformat() if row["associated_at"] else None
                }
                for row in iso_standards
            ],
            "count": len(iso_standards)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template ISO standards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/templates/{template_id}/iso-standards")
async def update_template_iso_standards(
    template_id: str,
    request: AssociateISORequest,
    current_user=Depends(get_current_user)
):
    """
    Update ISO standards for a template (replaces existing associations).

    Args:
        template_id: UUID of template
        request: List of ISO standard IDs

    Returns:
        Success message with updated ISO standards
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Verify template exists
            template_exists = await conn.fetchval(
                f"""
                SELECT EXISTS(
                    SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.templates
                    WHERE id = $1
                )
                """,
                uuid.UUID(template_id)
            )

            if not template_exists:
                raise HTTPException(status_code=404, detail="Template not found")

            # Verify all ISO standards exist
            for iso_id in request.iso_standard_ids:
                iso_exists = await conn.fetchval(
                    f"""
                    SELECT EXISTS(
                        SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.iso_standards
                        WHERE id = $1
                    )
                    """,
                    uuid.UUID(iso_id)
                )

                if not iso_exists:
                    raise HTTPException(
                        status_code=404,
                        detail=f"ISO standard {iso_id} not found"
                    )

            # Delete existing associations
            await conn.execute(
                f"""
                DELETE FROM {settings.DATABASE_APP_SCHEMA}.template_iso_standards
                WHERE template_id = $1
                """,
                uuid.UUID(template_id)
            )

            # Insert new associations
            for iso_id in request.iso_standard_ids:
                await conn.execute(
                    f"""
                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_iso_standards
                    (template_id, iso_standard_id, created_at)
                    VALUES ($1, $2, $3)
                    """,
                    uuid.UUID(template_id),
                    uuid.UUID(iso_id),
                    datetime.utcnow()
                )

            # Get updated ISO standards details
            iso_standards = await conn.fetch(
                f"""
                SELECT iso.id, iso.code, iso.name, iso.description
                FROM {settings.DATABASE_APP_SCHEMA}.iso_standards iso
                JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_standards tis
                ON iso.id = tis.iso_standard_id
                WHERE tis.template_id = $1
                """,
                uuid.UUID(template_id)
            )

        logger.info(f"Updated template {template_id} ISO associations to {len(request.iso_standard_ids)} standards")

        return {
            "message": f"Successfully updated template ISO associations to {len(request.iso_standard_ids)} standard(s)",
            "template_id": template_id,
            "iso_standards": [
                {
                    "id": str(row["id"]),
                    "code": row["code"],
                    "name": row["name"],
                    "description": row["description"]
                }
                for row in iso_standards
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template ISO standards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iso-standards/{iso_id}/templates")
async def get_iso_templates(
    iso_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get all templates associated with an ISO standard.

    Args:
        iso_id: UUID of ISO standard

    Returns:
        List of templates associated with this ISO standard
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            # Verify ISO standard exists
            iso_row = await conn.fetchrow(
                f"""
                SELECT id, code, name, description
                FROM {settings.DATABASE_APP_SCHEMA}.iso_standards
                WHERE id = $1
                """,
                uuid.UUID(iso_id)
            )

            if not iso_row:
                raise HTTPException(status_code=404, detail="ISO standard not found")

            # Get associated templates
            templates = await conn.fetch(
                f"""
                SELECT t.id, t.name, t.description, t.status,
                       t.created_at, t.updated_at,
                       tis.created_at as associated_at,
                       tf.filename as reference_document,
                       u.email as created_by_email
                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_standards tis
                ON t.id = tis.template_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.template_files tf
                ON t.template_file_id = tf.id
                LEFT JOIN auth.users u
                ON t.created_by = u.id
                WHERE tis.iso_standard_id = $1
                ORDER BY t.created_at DESC
                """,
                uuid.UUID(iso_id)
            )

        return {
            "iso_standard": {
                "id": str(iso_row["id"]),
                "code": iso_row["code"],
                "name": iso_row["name"],
                "description": iso_row["description"]
            },
            "templates": [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "description": row["description"],
                    "status": row["status"],
                    "reference_document": row["reference_document"],
                    "created_by": row["created_by_email"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    "associated_at": row["associated_at"].isoformat() if row["associated_at"] else None
                }
                for row in templates
            ],
            "count": len(templates)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ISO templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Task Status
# =============================================================================

@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get status of an analysis task.

    Args:
        task_id: UUID of task

    Returns:
        Task status and result (if completed)
    """
    try:
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            task_row = await conn.fetchrow(
                f"""
                SELECT id, status, progress, result, error, created_at, completed_at
                FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                WHERE id = $1
                """,
                uuid.UUID(task_id)
            )

            if not task_row:
                raise HTTPException(status_code=404, detail="Task not found")

            return {
                "task_id": str(task_row["id"]),
                "status": task_row["status"],
                "progress": task_row["progress"],
                "result": task_row["result"],
                "error": task_row["error"],
                "created_at": task_row["created_at"].isoformat() if task_row["created_at"] else None,
                "completed_at": task_row["completed_at"].isoformat() if task_row["completed_at"] else None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
