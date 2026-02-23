"""
Phase 3B: Task Resolution API
==============================
Task resolution workflow (answers, evidence, approvals)
"""

import logging
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import asyncpg

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Task Resolutions"])


# =====================================================
# Pydantic Models
# =====================================================

class ResolutionCreate(BaseModel):
    """Create task resolution."""
    resolution_type: str  # 'answer_provided', 'evidence_uploaded', 'manual_completion', etc.
    resolution_data: dict
    is_final: bool = True
    requires_approval: bool = False
    notes: Optional[str] = None


class ResolutionApproval(BaseModel):
    """Approve/reject resolution."""
    approved: bool
    quality_score: Optional[int] = None  # 1-5
    completeness_score: Optional[int] = None  # 0-100
    notes: Optional[str] = None


class ResolutionResponse(BaseModel):
    """Resolution response."""
    id: UUID
    task_id: UUID
    resolution_type: str
    resolution_data: dict
    is_final: bool
    requires_approval: bool
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    quality_score: Optional[int]
    completeness_score: Optional[int]
    resolved_by: int
    resolved_at: datetime
    notes: Optional[str]


# =====================================================
# Endpoints
# =====================================================

@router.post("/tasks/{task_id}/resolve", response_model=ResolutionResponse)
async def create_resolution(
    task_id: UUID,
    resolution: ResolutionCreate,
    user: dict = Depends(get_current_user)
):
    """
    Submit a resolution for a task.

    Resolution types:
    - answer_provided: Customer answered a question
    - evidence_uploaded: Customer uploaded evidence file
    - manual_completion: Manual task completed
    - clarification_requested: Need more information
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Verify task exists
                task_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM dna_app.customer_tasks WHERE id = $1)",
                    task_id
                )
                if not task_exists:
                    raise HTTPException(404, "Task not found")

                # Create resolution
                row = await conn.fetchrow("""
                    INSERT INTO dna_app.task_resolutions (
                        task_id, resolution_type, resolution_data, is_final,
                        requires_approval, resolved_by, notes
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id, task_id, resolution_type, resolution_data,
                              is_final, requires_approval, approved_at,
                              approved_by, quality_score, completeness_score,
                              resolved_by, resolved_at, notes
                """,
                    task_id, resolution.resolution_type, resolution.resolution_data,
                    resolution.is_final, resolution.requires_approval,
                    user.get("user_id"), resolution.notes
                )

                # Update task status based on resolution type
                if resolution.is_final and not resolution.requires_approval:
                    # Auto-complete if no approval needed
                    await conn.execute("""
                        UPDATE dna_app.customer_tasks
                        SET status = 'completed', completed_at = NOW(),
                            completed_by = $2, updated_at = NOW()
                        WHERE id = $1
                    """, task_id, user.get("user_id"))
                elif resolution.requires_approval:
                    # Set to under_review if approval needed
                    await conn.execute("""
                        UPDATE dna_app.customer_tasks
                        SET status = 'under_review', updated_at = NOW()
                        WHERE id = $1
                    """, task_id)

                logger.info(f"Resolution created: {row['id']} for task {task_id}")

                return ResolutionResponse(
                    id=row['id'],
                    task_id=row['task_id'],
                    resolution_type=row['resolution_type'],
                    resolution_data=row['resolution_data'],
                    is_final=row['is_final'],
                    requires_approval=row['requires_approval'],
                    approved_at=row['approved_at'],
                    approved_by=row['approved_by'],
                    quality_score=row['quality_score'],
                    completeness_score=row['completeness_score'],
                    resolved_by=row['resolved_by'],
                    resolved_at=row['resolved_at'],
                    notes=row['notes']
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating resolution: {e}")
        raise HTTPException(500, f"Failed to create resolution: {str(e)}")


@router.patch("/resolutions/{resolution_id}/approve", response_model=ResolutionResponse)
async def approve_resolution(
    resolution_id: UUID,
    approval: ResolutionApproval,
    user: dict = Depends(get_current_user)
):
    """
    Approve or reject a resolution.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get resolution and task
                resolution_row = await conn.fetchrow("""
                    SELECT task_id, requires_approval
                    FROM dna_app.task_resolutions
                    WHERE id = $1
                """, resolution_id)

                if not resolution_row:
                    raise HTTPException(404, "Resolution not found")

                if not resolution_row['requires_approval']:
                    raise HTTPException(400, "This resolution does not require approval")

                # Update resolution
                if approval.approved:
                    row = await conn.fetchrow("""
                        UPDATE dna_app.task_resolutions
                        SET is_final = true, approved_at = NOW(), approved_by = $2,
                            quality_score = $3, completeness_score = $4, notes = $5
                        WHERE id = $1
                        RETURNING id, task_id, resolution_type, resolution_data,
                                  is_final, requires_approval, approved_at,
                                  approved_by, quality_score, completeness_score,
                                  resolved_by, resolved_at, notes
                    """,
                        resolution_id, user.get("user_id"), approval.quality_score,
                        approval.completeness_score, approval.notes
                    )

                    # Mark task as completed
                    await conn.execute("""
                        UPDATE dna_app.customer_tasks
                        SET status = 'completed', completed_at = NOW(),
                            completed_by = $2, updated_at = NOW()
                        WHERE id = $1
                    """, resolution_row['task_id'], user.get("user_id"))

                    logger.info(f"Resolution approved: {resolution_id}")

                else:
                    # Rejected - mark resolution as not final
                    row = await conn.fetchrow("""
                        UPDATE dna_app.task_resolutions
                        SET is_final = false, notes = $2
                        WHERE id = $1
                        RETURNING id, task_id, resolution_type, resolution_data,
                                  is_final, requires_approval, approved_at,
                                  approved_by, quality_score, completeness_score,
                                  resolved_by, resolved_at, notes
                    """, resolution_id, approval.notes)

                    # Set task back to in_progress
                    await conn.execute("""
                        UPDATE dna_app.customer_tasks
                        SET status = 'in_progress', updated_at = NOW()
                        WHERE id = $1
                    """, resolution_row['task_id'])

                    logger.info(f"Resolution rejected: {resolution_id}")

                return ResolutionResponse(
                    id=row['id'],
                    task_id=row['task_id'],
                    resolution_type=row['resolution_type'],
                    resolution_data=row['resolution_data'],
                    is_final=row['is_final'],
                    requires_approval=row['requires_approval'],
                    approved_at=row['approved_at'],
                    approved_by=row['approved_by'],
                    quality_score=row['quality_score'],
                    completeness_score=row['completeness_score'],
                    resolved_by=row['resolved_by'],
                    resolved_at=row['resolved_at'],
                    notes=row['notes']
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving resolution: {e}")
        raise HTTPException(500, f"Failed to approve resolution: {str(e)}")


@router.get("/tasks/{task_id}/resolutions", response_model=List[ResolutionResponse])
async def list_task_resolutions(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """
    Get all resolutions for a task (resolution history).
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id, task_id, resolution_type, resolution_data, is_final,
                    requires_approval, approved_at, approved_by,
                    quality_score, completeness_score, resolved_by,
                    resolved_at, notes
                FROM dna_app.task_resolutions
                WHERE task_id = $1
                ORDER BY resolved_at DESC
            """, task_id)

            return [
                ResolutionResponse(
                    id=row['id'],
                    task_id=row['task_id'],
                    resolution_type=row['resolution_type'],
                    resolution_data=row['resolution_data'],
                    is_final=row['is_final'],
                    requires_approval=row['requires_approval'],
                    approved_at=row['approved_at'],
                    approved_by=row['approved_by'],
                    quality_score=row['quality_score'],
                    completeness_score=row['completeness_score'],
                    resolved_by=row['resolved_by'],
                    resolved_at=row['resolved_at'],
                    notes=row['notes']
                )
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Error listing resolutions: {e}")
        raise HTTPException(500, f"Failed to list resolutions: {str(e)}")
