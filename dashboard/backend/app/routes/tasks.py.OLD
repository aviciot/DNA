"""
Task Management API Routes
Endpoints for managing AI tasks and tracking progress
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..services import task_service
from ..auth import get_current_user


router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# Request/Response Models

class TaskStatusUpdate(BaseModel):
    """Request model for updating task status"""
    status: str = Field(..., pattern="^(processing|completed|failed|cancelled)$")
    progress: Optional[int] = Field(None, ge=0, le=100)
    current_step: Optional[str] = None
    error: Optional[str] = None


class TaskResponse(BaseModel):
    """Response model for task details"""
    id: str
    task_type: str
    related_id: Optional[str]
    status: str
    progress: int
    current_step: Optional[str]
    llm_provider: Optional[str]
    llm_model: Optional[str]
    result: Optional[dict]
    error: Optional[str]
    cost_usd: Optional[float]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    duration_seconds: Optional[int]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class TaskListItem(BaseModel):
    """Response model for task list items (summary)"""
    id: str
    task_type: str
    related_id: Optional[str]
    status: str
    progress: int
    current_step: Optional[str]
    llm_provider: Optional[str]
    error: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class TaskStatistics(BaseModel):
    """Response model for task statistics"""
    by_status: dict
    completed: dict


# API Endpoints

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed task information by ID
    
    Returns:
        Task details including status, progress, result, and metrics
    """
    task = await task_service.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    return task


@router.get("", response_model=List[TaskListItem])
async def list_tasks(
    status: Optional[str] = Query(None, pattern="^(pending|processing|completed|failed|cancelled)$"),
    task_type: Optional[str] = Query(None, pattern="^(template_parse|template_review|document_generate)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List tasks with optional filters
    
    Query Parameters:
        - status: Filter by task status
        - task_type: Filter by task type
        - limit: Maximum number of results (1-100, default: 50)
        - offset: Pagination offset (default: 0)
    
    Returns:
        List of tasks matching the filters
    """
    user_id = current_user.get('id')
    
    tasks = await task_service.list_tasks(
        user_id=user_id,
        status=status,
        task_type=task_type,
        limit=limit,
        offset=offset
    )
    
    return tasks


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a pending or processing task
    
    Returns:
        Success message if cancelled, error if task cannot be cancelled
    """
    success = await task_service.cancel_task(task_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Task not found or cannot be cancelled (already completed/failed)"
        )
    
    return {
        "success": True,
        "message": f"Task {task_id} cancelled successfully",
        "task_id": task_id
    }


@router.get("/statistics/overview", response_model=TaskStatistics)
async def get_task_statistics(
    current_user: dict = Depends(get_current_user)
):
    """
    Get overall task statistics
    
    Returns:
        Task counts by status, average duration, total costs, token usage
    """
    stats = await task_service.get_task_statistics()
    return stats


# Internal endpoint (no auth required, for AI workers)
@router.post("/{task_id}/progress", include_in_schema=False)
async def update_task_progress(
    task_id: str,
    status: str = Query(..., pattern="^(processing|completed|failed)$"),
    progress: Optional[int] = Query(None, ge=0, le=100),
    current_step: Optional[str] = None,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    cost_usd: Optional[float] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None
):
    """
    Internal endpoint for AI workers to update task progress
    This endpoint is not included in public API docs
    """
    success = await task_service.update_task_status(
        task_id=task_id,
        status=status,
        progress=progress,
        current_step=current_step,
        result=result,
        error=error,
        cost_usd=cost_usd,
        tokens_input=tokens_input,
        tokens_output=tokens_output
    )
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    # Publish progress update to Redis Pub/Sub
    if progress is not None or current_step:
        await task_service.publish_progress(task_id, {
            'status': status,
            'progress': progress,
            'current_step': current_step,
            'error': error
        })
    
    return {"success": True, "task_id": task_id, "status": status}
