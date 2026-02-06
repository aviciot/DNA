"""
Task Service - AI Task Management
Handles task creation, updates, and Redis Stream/Pub-Sub integration
"""
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncpg

from ..redis_client import redis_client
from ..database import get_db_pool
from ..config import settings


async def create_task(
    task_type: str,
    related_id: Optional[str] = None,
    llm_provider: Optional[str] = None,
    created_by: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new AI task and publish to Redis Stream
    
    Args:
        task_type: Type of task ('template_parse', 'template_review', 'document_generate')
        related_id: UUID of related entity (template_id, document_id)
        llm_provider: Name of LLM provider to use (default: use default_parser)
        created_by: User ID who created the task
        metadata: Additional task metadata (file_path, custom_rules, etc.)
    
    Returns:
        Task record with id, status, and created_at
    """
    task_id = str(uuid.uuid4())
    pool = await get_db_pool()
    
    # Get LLM provider details
    async with pool.acquire() as conn:
        if llm_provider:
            provider_row = await conn.fetchrow(
                "SELECT id, name, model FROM dna_app.llm_providers WHERE name = $1 AND enabled = true",
                llm_provider
            )
        else:
            # Use default parser
            provider_row = await conn.fetchrow(
                "SELECT id, name, model FROM dna_app.llm_providers WHERE is_default_parser = true AND enabled = true"
            )
        
        if not provider_row:
            raise ValueError(f"No enabled LLM provider found: {llm_provider or 'default_parser'}")
        
        # Create task record
        await conn.execute(
            """INSERT INTO dna_app.ai_tasks 
               (id, task_type, related_id, status, llm_provider_id, llm_provider, llm_model, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            task_id,
            task_type,
            related_id,
            'pending',
            provider_row['id'],
            provider_row['name'],
            provider_row['model'],
            created_by
        )
        
        # Get created task
        task = await conn.fetchrow(
            "SELECT id, task_type, status, progress, created_at FROM dna_app.ai_tasks WHERE id = $1",
            task_id
        )
    
    # Publish to Redis Stream
    stream_name = get_stream_name(task_type)
    stream_data = {
        'task_id': task_id,
        'task_type': task_type,
        'related_id': related_id or '',
        'llm_provider': provider_row['name'],
        'llm_model': provider_row['model'],
        'created_by': str(created_by) if created_by else '',
        'created_at': datetime.utcnow().isoformat(),
        **(metadata or {})
    }
    
    message_id = await redis_client.add_to_stream(stream_name, stream_data)
    
    return {
        'id': str(task['id']),
        'task_type': task['task_type'],
        'status': task['status'],
        'progress': task['progress'],
        'created_at': task['created_at'].isoformat(),
        'stream_message_id': message_id
    }


async def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get task details by ID
    
    Args:
        task_id: Task UUID
    
    Returns:
        Task record or None if not found
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        task = await conn.fetchrow(
            """SELECT id, task_type, related_id, status, progress, current_step,
                      llm_provider, llm_model, result, error, cost_usd,
                      tokens_input, tokens_output, duration_seconds,
                      created_at, started_at, completed_at
               FROM dna_app.ai_tasks 
               WHERE id = $1""",
            task_id
        )
        
        if not task:
            return None
        
        return {
            'id': str(task['id']),
            'task_type': task['task_type'],
            'related_id': str(task['related_id']) if task['related_id'] else None,
            'status': task['status'],
            'progress': task['progress'],
            'current_step': task['current_step'],
            'llm_provider': task['llm_provider'],
            'llm_model': task['llm_model'],
            'result': task['result'],
            'error': task['error'],
            'cost_usd': float(task['cost_usd']) if task['cost_usd'] else None,
            'tokens_input': task['tokens_input'],
            'tokens_output': task['tokens_output'],
            'duration_seconds': task['duration_seconds'],
            'created_at': task['created_at'].isoformat(),
            'started_at': task['started_at'].isoformat() if task['started_at'] else None,
            'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None
        }


async def list_tasks(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List tasks with optional filters
    
    Args:
        user_id: Filter by user who created task
        status: Filter by task status
        task_type: Filter by task type
        limit: Maximum number of results
        offset: Pagination offset
    
    Returns:
        List of task records
    """
    pool = await get_db_pool()
    
    # Build query
    query = """
        SELECT id, task_type, related_id, status, progress, current_step,
               llm_provider, error, created_at, started_at, completed_at
        FROM dna_app.ai_tasks
        WHERE 1=1
    """
    params = []
    param_count = 0
    
    if user_id:
        param_count += 1
        query += f" AND created_by = ${param_count}"
        params.append(user_id)
    
    if status:
        param_count += 1
        query += f" AND status = ${param_count}"
        params.append(status)
    
    if task_type:
        param_count += 1
        query += f" AND task_type = ${param_count}"
        params.append(task_type)
    
    query += " ORDER BY created_at DESC"
    
    param_count += 1
    query += f" LIMIT ${param_count}"
    params.append(limit)
    
    param_count += 1
    query += f" OFFSET ${param_count}"
    params.append(offset)
    
    async with pool.acquire() as conn:
        tasks = await conn.fetch(query, *params)
        
        return [
            {
                'id': str(task['id']),
                'task_type': task['task_type'],
                'related_id': str(task['related_id']) if task['related_id'] else None,
                'status': task['status'],
                'progress': task['progress'],
                'current_step': task['current_step'],
                'llm_provider': task['llm_provider'],
                'error': task['error'],
                'created_at': task['created_at'].isoformat(),
                'started_at': task['started_at'].isoformat() if task['started_at'] else None,
                'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None
            }
            for task in tasks
        ]


async def update_task_status(
    task_id: str,
    status: str,
    progress: Optional[int] = None,
    current_step: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    cost_usd: Optional[float] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None
) -> bool:
    """
    Update task status and optionally other fields
    
    Args:
        task_id: Task UUID
        status: New status ('processing', 'completed', 'failed', 'cancelled')
        progress: Progress percentage (0-100)
        current_step: Current processing step description
        result: Task result data (for completed tasks)
        error: Error message (for failed tasks)
        cost_usd: API cost
        tokens_input: Input tokens used
        tokens_output: Output tokens used
    
    Returns:
        True if updated successfully, False if task not found
    """
    pool = await get_db_pool()
    
    # Build dynamic update query
    updates = ["status = $2"]
    params = [task_id, status]
    param_count = 2
    
    if progress is not None:
        param_count += 1
        updates.append(f"progress = ${param_count}")
        params.append(progress)
    
    if current_step is not None:
        param_count += 1
        updates.append(f"current_step = ${param_count}")
        params.append(current_step)
    
    if result is not None:
        param_count += 1
        updates.append(f"result = ${param_count}")
        params.append(json.dumps(result))
    
    if error is not None:
        param_count += 1
        updates.append(f"error = ${param_count}")
        params.append(error)
    
    if cost_usd is not None:
        param_count += 1
        updates.append(f"cost_usd = ${param_count}")
        params.append(cost_usd)
    
    if tokens_input is not None:
        param_count += 1
        updates.append(f"tokens_input = ${param_count}")
        params.append(tokens_input)
    
    if tokens_output is not None:
        param_count += 1
        updates.append(f"tokens_output = ${param_count}")
        params.append(tokens_output)
    
    # Add timestamps
    if status == 'processing' and 'started_at' not in updates:
        updates.append("started_at = NOW()")
    
    if status in ('completed', 'failed', 'cancelled'):
        updates.append("completed_at = NOW()")
        
        # Calculate duration
        updates.append("duration_seconds = EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, created_at)))::INTEGER")
    
    query = f"UPDATE dna_app.ai_tasks SET {', '.join(updates)} WHERE id = $1"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        
        # Check if any row was updated
        return result.split()[-1] == '1'


async def cancel_task(task_id: str) -> bool:
    """
    Cancel a pending or processing task
    
    Args:
        task_id: Task UUID
    
    Returns:
        True if cancelled successfully, False if task not found or already completed
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Only cancel if task is pending or processing
        result = await conn.execute(
            """UPDATE dna_app.ai_tasks 
               SET status = 'cancelled', completed_at = NOW(),
                   duration_seconds = EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, created_at)))::INTEGER
               WHERE id = $1 AND status IN ('pending', 'processing')""",
            task_id
        )
        
        return result.split()[-1] == '1'


async def publish_progress(task_id: str, progress_data: Dict[str, Any]) -> int:
    """
    Publish task progress update to Redis Pub/Sub
    
    Args:
        task_id: Task UUID
        progress_data: Progress update data (progress, current_step, etc.)
    
    Returns:
        Number of subscribers who received the message
    """
    channel = f"progress:task:{task_id}"
    
    message = {
        'task_id': task_id,
        'timestamp': datetime.utcnow().isoformat(),
        **progress_data
    }
    
    return await redis_client.publish(channel, message)


def get_stream_name(task_type: str) -> str:
    """
    Get Redis Stream name for task type
    
    Args:
        task_type: Task type
    
    Returns:
        Stream name
    """
    stream_mapping = {
        'template_parse': 'template:parse',
        'template_review': 'template:review',
        'document_generate': 'document:generate'
    }
    
    return stream_mapping.get(task_type, 'task:default')


async def get_task_statistics() -> Dict[str, Any]:
    """
    Get overall task statistics
    
    Returns:
        Statistics including counts by status, average duration, costs
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Count by status
        status_counts = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM dna_app.ai_tasks GROUP BY status"
        )
        
        # Average metrics for completed tasks
        metrics = await conn.fetchrow(
            """SELECT 
                   COUNT(*) as total_completed,
                   AVG(duration_seconds) as avg_duration,
                   SUM(cost_usd) as total_cost,
                   AVG(cost_usd) as avg_cost,
                   SUM(tokens_input) as total_tokens_input,
                   SUM(tokens_output) as total_tokens_output
               FROM dna_app.ai_tasks 
               WHERE status = 'completed'"""
        )
        
        return {
            'by_status': {row['status']: row['count'] for row in status_counts},
            'completed': {
                'total': metrics['total_completed'] or 0,
                'avg_duration_seconds': float(metrics['avg_duration']) if metrics['avg_duration'] else 0,
                'total_cost_usd': float(metrics['total_cost']) if metrics['total_cost'] else 0,
                'avg_cost_usd': float(metrics['avg_cost']) if metrics['avg_cost'] else 0,
                'total_tokens_input': metrics['total_tokens_input'] or 0,
                'total_tokens_output': metrics['total_tokens_output'] or 0
            }
        }
