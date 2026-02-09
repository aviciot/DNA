"""
Database Client for AI Service
===============================

Handles PostgreSQL connections for reading tasks and writing results.
"""

import json
import logging
from typing import Optional, Dict, Any
import asyncpg
from config import settings

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Async PostgreSQL client for AI service."""

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Initialize database connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=settings.DATABASE_HOST,
                port=settings.DATABASE_PORT,
                database=settings.DATABASE_NAME,
                user=settings.DATABASE_USER,
                password=settings.DATABASE_PASSWORD,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info(f"Database pool created: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")

    async def disconnect(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")

    async def fetch_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch task by ID from ai_tasks table.

        Args:
            task_id: Task UUID

        Returns:
            Task record as dictionary or None if not found
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT
                        id, task_type, related_id, status, progress, current_step,
                        llm_provider_id, llm_provider, llm_model, result, error,
                        cost_usd, tokens_input, tokens_output, duration_seconds,
                        created_at, started_at, completed_at, created_by
                    FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks
                    WHERE id = $1
                    """,
                    task_id
                )

                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Failed to fetch task {task_id}: {e}")
            raise

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Update task status and progress.

        Args:
            task_id: Task UUID
            status: New status (pending, processing, completed, failed, cancelled)
            progress: Progress percentage (0-100)
            current_step: Current step description
            error: Error message if failed
        """
        try:
            async with self._pool.acquire() as conn:
                query = f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.ai_tasks
                SET
                    status = $2::VARCHAR,
                    progress = COALESCE($3, progress),
                    current_step = COALESCE($4::TEXT, current_step),
                    error = COALESCE($5::TEXT, error),
                    started_at = CASE WHEN $2 = 'processing' AND started_at IS NULL THEN NOW() ELSE started_at END,
                    completed_at = CASE WHEN $2 IN ('completed', 'failed', 'cancelled') THEN NOW() ELSE completed_at END
                WHERE id = $1
                """
                await conn.execute(query, task_id, status, progress, current_step, error)
                logger.debug(f"Updated task {task_id}: status={status}, progress={progress}")

        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            raise

    async def save_task_result(
        self,
        task_id: str,
        result: Dict[str, Any],
        cost_usd: Optional[float] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        duration_seconds: Optional[int] = None
    ):
        """
        Save task result and metrics.

        Args:
            task_id: Task UUID
            result: Result data as dictionary (will be stored as JSONB)
            cost_usd: API cost in USD
            tokens_input: Input tokens used
            tokens_output: Output tokens used
            duration_seconds: Task duration in seconds
        """
        try:
            async with self._pool.acquire() as conn:
                query = f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.ai_tasks
                SET
                    status = 'completed',
                    progress = 100,
                    result = $2::JSONB,
                    cost_usd = COALESCE($3, cost_usd),
                    tokens_input = COALESCE($4, tokens_input),
                    tokens_output = COALESCE($5, tokens_output),
                    duration_seconds = COALESCE($6, duration_seconds),
                    completed_at = NOW()
                WHERE id = $1
                """
                # Convert dict to JSON string for JSONB column
                result_json = json.dumps(result) if isinstance(result, dict) else result

                await conn.execute(
                    query,
                    task_id,
                    result_json,
                    cost_usd,
                    tokens_input,
                    tokens_output,
                    duration_seconds
                )
                logger.info(f"Saved result for task {task_id} (cost: ${cost_usd}, tokens: {tokens_input}/{tokens_output})")

        except Exception as e:
            logger.error(f"Failed to save task result {task_id}: {e}")
            raise

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get template by ID from templates table.

        Args:
            template_id: Template UUID

        Returns:
            Template structure (JSON) or None if not found
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT
                        id, name, iso_standard, version, structure, metadata,
                        created_at, updated_at, created_by
                    FROM {settings.DATABASE_APP_SCHEMA}.templates
                    WHERE id = $1
                    """,
                    template_id
                )

                if row:
                    # Return the structure (JSONB field containing full template)
                    template = dict(row)
                    # The 'structure' field contains the full parsed template JSON
                    return template.get('structure', {})
                return None

        except Exception as e:
            logger.error(f"Failed to fetch template {template_id}: {e}")
            raise

    async def get_llm_provider(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get LLM provider configuration by name.

        Args:
            provider_name: Provider name (e.g., 'claude', 'openai')

        Returns:
            Provider configuration or None if not found
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT
                        id, name, display_name, model, api_key_env,
                        cost_per_1k_input, cost_per_1k_output, max_tokens, enabled
                    FROM {settings.DATABASE_APP_SCHEMA}.llm_providers
                    WHERE name = $1 AND enabled = true
                    """,
                    provider_name
                )

                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Failed to fetch LLM provider {provider_name}: {e}")
            raise

    async def create_template(
        self,
        name: str,
        description: Optional[str],
        template_file_id: str,
        template_structure: Dict[str, Any],
        ai_task_id: str,
        iso_standard: Optional[str] = None
    ) -> str:
        """
        Create a new template with fixed/fillable sections (CORRECT APPROACH).

        Args:
            name: Template name
            description: Template description
            template_file_id: Reference file UUID
            template_structure: Template with fixed_sections and fillable_sections
            ai_task_id: AI task UUID that created this template
            iso_standard: ISO standard identifier (e.g., "ISMS 10")

        Returns:
            UUID of created template

        Template structure format:
        {
            "document_title": "...",
            "fixed_sections": [...],
            "fillable_sections": [...],
            "metadata": {
                "total_fixed_sections": N,
                "total_fillable_sections": M,
                "semantic_tags_used": [...]
            }
        }
        """
        try:
            async with self._pool.acquire() as conn:
                # Convert dict to JSON string for JSONB column
                structure_json = json.dumps(template_structure) if isinstance(template_structure, dict) else template_structure

                # Extract statistics from template_structure
                metadata = template_structure.get('metadata', {})
                total_fixed = metadata.get('total_fixed_sections', 0)
                total_fillable = metadata.get('total_fillable_sections', 0)
                semantic_tags = metadata.get('semantic_tags_used', [])

                row = await conn.fetchrow(
                    f"""
                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.templates (
                        name,
                        description,
                        iso_standard,
                        template_file_id,
                        template_structure,
                        ai_task_id,
                        status,
                        total_fixed_sections,
                        total_fillable_sections,
                        semantic_tags,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5::JSONB, $6, 'draft', $7, $8, $9, NOW())
                    RETURNING id
                    """,
                    name,
                    description,
                    iso_standard,
                    template_file_id,
                    structure_json,
                    ai_task_id,
                    total_fixed,
                    total_fillable,
                    semantic_tags
                )

                template_id = str(row['id'])
                logger.info(f"Created template {template_id}: {name} ({total_fixed} fixed, {total_fillable} fillable)")
                return template_id

        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            raise


# Global database client instance
db_client = DatabaseClient()


async def get_db() -> DatabaseClient:
    """Dependency for getting database client."""
    if db_client._pool is None:
        await db_client.connect()
    return db_client
