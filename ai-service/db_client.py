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


# ── ISO360 DB helpers (module-level, parallel to automation-service/db_client.py) ──


import base64 as _b64
import hashlib as _hs


def _decrypt_credential(value: str) -> str:
    """Decrypt a Fernet-encrypted credential stored as 'enc:<token>'."""
    if not value or not value.startswith("enc:"):
        return value
    try:
        from cryptography.fernet import Fernet
        raw_key = settings.SECRET_KEY.encode()
        key = _b64.urlsafe_b64encode(_hs.sha256(raw_key).digest())
        return Fernet(key).decrypt(value[4:].encode()).decode()
    except Exception:
        return value


async def get_ai_config_for_service(service_name: str) -> dict:
    """Get AI provider/model/api_key for a given service from ai_config + llm_providers."""
    async with db_client._pool.acquire() as conn:
        ai_row = await conn.fetchrow(
            f"SELECT provider, model FROM {settings.DATABASE_APP_SCHEMA}.ai_config WHERE service = $1",
            service_name,
        )
    provider = (ai_row["provider"] if ai_row else None) or "gemini"
    model    = (ai_row["model"]    if ai_row else None) or "gemini-2.5-flash"

    async with db_client._pool.acquire() as conn:
        prow = await conn.fetchrow(
            f"SELECT api_key FROM {settings.DATABASE_APP_SCHEMA}.llm_providers"
            f" WHERE name = $1 AND enabled = true",
            provider,
        )
    api_key = _decrypt_credential(prow["api_key"] or "") if prow and prow["api_key"] else ""
    return {"provider": provider, "model": model, "_api_key": api_key}


async def get_ai_prompt(prompt_key: str) -> dict | None:
    """Fetch a prompt from ai_prompts by key."""
    async with db_client._pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.ai_prompts"
            f" WHERE prompt_key = $1 AND is_active = TRUE",
            prompt_key,
        )
    return dict(row) if row else None


async def get_iso_standard_with_placeholders(iso_standard_id: str) -> dict | None:
    """Return ISO standard row with parsed placeholder_dictionary."""
    async with db_client._pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT id, code, name, placeholder_dictionary"
            f" FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1",
            iso_standard_id,
        )
    if not row:
        return None
    result = dict(row)
    raw = result.get("placeholder_dictionary")
    if isinstance(raw, str):
        try:
            result["placeholder_dictionary"] = json.loads(raw)
        except Exception:
            result["placeholder_dictionary"] = []
    return result


async def get_iso_recurring_activities(iso_standard_id: str) -> list:
    """
    Collect all recurring activities for an ISO standard from two sources:
      1. recurring_activities JSONB on each linked catalog template (per-template activities)
      2. iso360_recurring_activities JSONB on the iso_standards row (cross-cutting)
    Returns a merged, deduplicated list by 'key'.
    Returns empty list if no recurring_activities have been populated yet.
    """
    async with db_client._pool.acquire() as conn:
        # Per-template activities
        tmpl_rows = await conn.fetch(
            f"""
            SELECT t.id, t.name, t.recurring_activities
            FROM {settings.DATABASE_APP_SCHEMA}.templates t
            JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping m ON m.template_id = t.id
            WHERE m.iso_standard_id = $1
              AND t.recurring_activities IS NOT NULL
              AND jsonb_array_length(COALESCE(t.recurring_activities, '[]'::jsonb)) > 0
            """,
            iso_standard_id,
        )
        # ISO-level cross-cutting activities
        std_row = await conn.fetchrow(
            f"SELECT iso360_recurring_activities FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1",
            iso_standard_id,
        )

    seen_keys = set()
    activities = []

    # Per-template first
    for row in tmpl_rows:
        raw = row["recurring_activities"]
        acts = json.loads(raw) if isinstance(raw, str) else (raw or [])
        for act in acts:
            if not isinstance(act, dict):
                continue
            key = act.get("key")
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            activities.append({
                **act,
                "template_name": row["name"],
                "template_id": str(row["id"]),
                "source": "template",
            })

    # ISO-level cross-cutting
    if std_row and std_row["iso360_recurring_activities"]:
        raw = std_row["iso360_recurring_activities"]
        iso_acts = json.loads(raw) if isinstance(raw, str) else (raw or [])
        for act in iso_acts:
            if not isinstance(act, dict):
                continue
            key = act.get("key")
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            activities.append({
                **act,
                "template_name": None,
                "template_id": None,
                "source": "iso_level",
            })

    return activities


async def get_iso360_template_by_key(placeholder_key: str) -> dict | None:
    """Return existing iso360_template for a placeholder_key, or None."""
    async with db_client._pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.iso360_templates"
            f" WHERE placeholder_key = $1",
            placeholder_key,
        )
    return dict(row) if row else None


async def create_iso360_template(
    placeholder_key: str, type_: str, update_frequency: str,
    title: str, responsible_role: str, steps: list, evidence_fields: list,
) -> str:
    """Insert a new iso360_template and return its UUID string."""
    async with db_client._pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.iso360_templates
                (placeholder_key, type, update_frequency, title, responsible_role, steps, evidence_fields)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                RETURNING id""",
            placeholder_key, type_, update_frequency, title, responsible_role,
            json.dumps(steps), json.dumps(evidence_fields),
        )
    return str(row["id"])


async def link_iso360_template_to_standard(
    template_id: str, iso_standard_id: str, covered_clauses: list | None = None,
) -> None:
    """Insert into iso360_template_iso_mapping (idempotent — ON CONFLICT DO NOTHING)."""
    async with db_client._pool.acquire() as conn:
        await conn.execute(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.iso360_template_iso_mapping
                (template_id, iso_standard_id, covered_clauses)
                VALUES ($1, $2, $3)
                ON CONFLICT (template_id, iso_standard_id) DO NOTHING""",
            template_id, iso_standard_id, covered_clauses or [],
        )


async def get_iso360_templates_for_standard(iso_standard_id: str) -> list:
    """Return all iso360_templates linked to the given ISO standard, with parsed JSONB."""
    async with db_client._pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT t.*
                FROM {settings.DATABASE_APP_SCHEMA}.iso360_templates t
                JOIN {settings.DATABASE_APP_SCHEMA}.iso360_template_iso_mapping m
                     ON m.template_id = t.id
                WHERE m.iso_standard_id = $1::uuid
                ORDER BY t.placeholder_key""",
            iso_standard_id,
        )
    result = []
    for r in rows:
        d = dict(r)
        d["steps"]           = json.loads(d["steps"])           if isinstance(d.get("steps"), str)           else (d.get("steps") or [])
        d["evidence_fields"] = json.loads(d["evidence_fields"]) if isinstance(d.get("evidence_fields"), str) else (d.get("evidence_fields") or [])
        result.append(d)
    return result


async def get_customer_answers_context(customer_id: int, plan_id: str) -> str:
    """Return a formatted string of all answered/completed tasks for LLM context."""
    async with db_client._pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT placeholder_key, answer
                FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2
                  AND status IN ('answered', 'completed')
                  AND answer IS NOT NULL""",
            customer_id, plan_id,
        )
    if not rows:
        return ""
    return "\n".join(f"{r['placeholder_key']}: {r['answer']}" for r in rows)


async def get_customer_info(customer_id: int) -> dict:
    """Return {industry, size} for a customer — uses description as fallback."""
    async with db_client._pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
            customer_id,
        )
    if not row:
        return {"industry": "", "size": ""}
    r = dict(row)
    industry = r.get("industry") or r.get("sector") or ""
    size = r.get("company_size") or r.get("size") or r.get("employees") or ""
    # Fallback: pull a hint from description if available
    if not industry and r.get("description"):
        industry = (r["description"] or "")[:100]
    return {"industry": str(industry), "size": str(size)}


async def save_iso360_customer_document(
    customer_id: int,
    plan_id: str,
    iso_standard_id: str,
    template: dict,
    personalized_content: dict,
    next_due_date,  # date | None
) -> str:
    """Insert a customer_document row for an ISO360 activity.
    Idempotent: skips insert if a row with this iso360_template_id already exists for the plan.
    Returns the document UUID string.
    """
    template_id = str(template["id"])
    async with db_client._pool.acquire() as conn:
        # Idempotency check
        existing = await conn.fetchval(
            f"""SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_documents
                WHERE plan_id = $1::uuid AND iso360_template_id = $2::uuid""",
            plan_id, template_id,
        )
        if existing:
            return str(existing)

        row = await conn.fetchrow(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_documents
                (customer_id, plan_id, iso360_template_id,
                 template_name, document_name, document_type,
                 iso_code, status, content, next_due_date)
                VALUES ($1, $2::uuid, $3::uuid, $4, $5, 'iso360_activity',
                        $6, 'active', $7::jsonb, $8)
                RETURNING id""",
            customer_id, plan_id, template_id,
            personalized_content.get("title") or template.get("title", ""),
            personalized_content.get("title") or template.get("title", ""),
            iso_standard_id,
            json.dumps(personalized_content),
            next_due_date,
        )
    return str(row["id"])


async def mark_adjustment_pass_done(plan_id: str) -> None:
    """Set adjustment_pass_done=TRUE in iso360_plan_settings for this plan."""
    async with db_client._pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.iso360_plan_settings
                SET adjustment_pass_done = TRUE, updated_at = NOW()
                WHERE plan_id = $1::uuid""",
            plan_id,
        )
