"""Async PostgreSQL client for automation service."""
import base64
import hashlib
import asyncpg
import logging
from config import settings

# ── Credential decryption (mirror of backend logic) ──────────────────────────
_ENCRYPTED_PREFIX = "enc:"


def _decrypt_credential(value: str) -> str:
    """Decrypt a Fernet-encrypted credential stored as 'enc:<token>'."""
    if not value or not value.startswith(_ENCRYPTED_PREFIX):
        return value
    try:
        from cryptography.fernet import Fernet
        raw_key = settings.SECRET_KEY.encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
        return Fernet(key).decrypt(value[len(_ENCRYPTED_PREFIX):].encode()).decode()
    except Exception:
        return value

logger = logging.getLogger(__name__)
_pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("DB pool created")
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_automation_config() -> dict:
    """Load automation config + resolve LLM key from central tables."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.automation_config WHERE id = 1"
        )
        ai_row = await conn.fetchrow(
            f"SELECT provider, model"
            f" FROM {settings.DATABASE_APP_SCHEMA}.ai_config WHERE service = 'extraction'"
        )
    if not row:
        return {}
    cfg = dict(row)
    for field in ("gmail_app_password", "sendgrid_api_key"):
        if cfg.get(field):
            cfg[field] = _decrypt_credential(cfg[field])

    # Resolve extraction provider/model from ai_config
    provider = (ai_row["provider"] if ai_row else None) or "gemini"
    extraction_model = (ai_row["model"] if ai_row else None) or "gemini-2.5-flash"
    cfg["extraction_provider"] = provider
    cfg["extraction_model"] = extraction_model

    # Resolve API key from llm_providers
    async with pool.acquire() as conn:
        prow = await conn.fetchrow(
            f"SELECT api_key FROM {settings.DATABASE_APP_SCHEMA}.llm_providers"
            f" WHERE name = $1 AND enabled = true",
            provider,
        )
    if prow and prow["api_key"]:
        cfg["_api_key"] = _decrypt_credential(prow["api_key"] or "")

    return cfg


async def get_customer_automation_config(customer_id: int) -> dict | None:
    """Load per-customer automation overrides (contact_name, language, send_to_emails, etc.)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customer_automation_config WHERE customer_id = $1",
            customer_id,
        )
    return dict(row) if row else None


async def get_customer_by_id(customer_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
            customer_id,
        )
    return dict(row) if row else None


async def get_portal_token(customer_id: int) -> str | None:
    """Return the customer's portal access token, or None if not found/expired."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT token FROM {settings.DATABASE_APP_SCHEMA}.customer_portal_access"
            f" WHERE customer_id = $1 AND expires_at > NOW()",
            customer_id,
        )
    return row["token"] if row else None


async def get_customer_by_email(email: str) -> dict | None:
    """Find customer whose any email field matches."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customers
                WHERE email = $1 OR contact_email = $1
                   OR compliance_email = $1 OR document_email = $1
                   OR contract_email = $1
                LIMIT 1""",
            email,
        )
    return dict(row) if row else None


async def get_pending_tasks_for_plan(customer_id: int, plan_id: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT ct.*, t.name AS template_name
                FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.templates t ON t.id = ct.template_id
                WHERE ct.customer_id = $1
                  AND ct.plan_id = $2
                  AND ct.status IN ('pending', 'in_progress')
                  AND (ct.is_ignored = false OR ct.is_ignored IS NULL)
                  AND COALESCE(ct.requires_followup, TRUE) = TRUE
                ORDER BY ct.priority DESC, ct.created_at""",
            customer_id, plan_id,
        )
    return [dict(r) for r in rows]


async def get_pending_notification_tasks(limit: int = 20) -> list:
    """Return pending notification tasks ordered by creation time, up to limit."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT ct.*, c.name AS customer_name, c.email AS customer_email,
                       c.contact_email, c.compliance_email,
                       c.description AS customer_description,
                       cpa.token AS portal_token
                FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                JOIN {settings.DATABASE_APP_SCHEMA}.customers c ON c.id = ct.customer_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_portal_access cpa
                       ON cpa.customer_id = ct.customer_id AND cpa.expires_at > NOW()
                WHERE ct.task_type = 'notification'
                  AND ct.status = 'pending'
                  AND COALESCE(ct.retry_count, 0) < 3
                ORDER BY ct.created_at
                LIMIT $1""",
            limit,
        )
    return [dict(r) for r in rows]


async def get_ai_prompt(prompt_key: str) -> dict | None:
    """Fetch a prompt from ai_prompts by key."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.ai_prompts"
            f" WHERE prompt_key = $1 AND is_active = TRUE",
            prompt_key,
        )
    return dict(row) if row else None


async def complete_notification_task(task_id: str, email_address: str, metadata: dict = None) -> None:
    """Mark a notification task as completed and log the successful send."""
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET status = 'completed', last_error = NULL, updated_at = NOW()
                WHERE id = $1""",
            task_id,
        )
        attempt = await conn.fetchval(
            f"SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM {settings.DATABASE_APP_SCHEMA}.task_execution_log WHERE task_id = $1",
            task_id,
        )
        await conn.execute(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.task_execution_log
                (task_id, attempt_number, status, email_address, metadata)
                VALUES ($1, $2, 'succeeded', $3, $4::jsonb)""",
            task_id, attempt, email_address, _json.dumps(metadata or {}),
        )


async def fail_notification_task(task_id: str, error: str, email_address: str = None, metadata: dict = None) -> None:
    """Increment retry_count, store last_error, log the failed attempt."""
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET last_error = $2,
                    retry_count = COALESCE(retry_count, 0) + 1,
                    status = CASE WHEN COALESCE(retry_count, 0) + 1 >= 3 THEN 'failed' ELSE 'pending' END,
                    updated_at = NOW()
                WHERE id = $1""",
            task_id, error,
        )
        attempt = await conn.fetchval(
            f"SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM {settings.DATABASE_APP_SCHEMA}.task_execution_log WHERE task_id = $1",
            task_id,
        )
        await conn.execute(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.task_execution_log
                (task_id, attempt_number, status, email_address, error_message, metadata)
                VALUES ($1, $2, 'failed', $3, $4, $5::jsonb)""",
            task_id, attempt, email_address, error, _json.dumps(metadata or {}),
        )


async def get_collection_request_by_token(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests WHERE token = $1",
            token,
        )
    return dict(row) if row else None


async def get_collection_request_by_short_code(short_code: str) -> dict | None:
    """Find the most recent pending request whose token starts with the 8-char reference code.

    Used when the customer includes 'DNA-XXXXXXXX' in the body of a new email thread.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT * FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests
                WHERE LEFT(token, 8) = $1
                ORDER BY sent_at DESC
                LIMIT 1""",
            short_code.lower(),
        )
    return dict(row) if row else None


async def create_collection_request(
    customer_id: int, plan_id: str, token: str,
    questions_snapshot: list, evidence_snapshot: list,
    sent_to: list, subject: str, campaign_number: int = 1,
    parent_request_id: str | None = None, created_by: int | None = None,
) -> str:
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.email_collection_requests
                (customer_id, plan_id, token, campaign_number, parent_request_id,
                 questions_snapshot, evidence_snapshot, sent_to, subject,
                 status, sent_at, expires_at, created_by)
                VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8,$9,'pending',NOW(),NOW()+INTERVAL '7 days',$10)
                RETURNING id""",
            customer_id, plan_id, token, campaign_number, parent_request_id,
            json.dumps(questions_snapshot), json.dumps(evidence_snapshot),
            sent_to, subject, created_by,
        )
    return str(row["id"])


async def create_inbound_log(
    collection_request_id: str | None, customer_id: int | None,
    from_email: str, subject: str, body_text: str, body_html: str,
    attachments: list,
) -> str:
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.email_inbound_log
                (collection_request_id, customer_id, from_email, subject,
                 body_text, body_html, attachments, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,'received')
                RETURNING id""",
            collection_request_id, customer_id,
            from_email, subject, body_text, body_html,
            json.dumps(attachments),
        )
    return str(row["id"])


async def update_inbound_log_status(log_id: str, status: str, extraction_result: dict | None = None):
    import json
    pool = await get_pool()
    result_json = json.dumps(extraction_result) if extraction_result else None
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_inbound_log
                SET status = $2,
                    -- Only overwrite extraction_result when we actually have one;
                    -- the final 'applied' update must not clear the LLM result
                    extraction_result = COALESCE($3::jsonb, extraction_result),
                    processed_at = NOW()
                WHERE id = $1""",
            log_id, status, result_json,
        )


async def create_extraction_items(items: list) -> None:
    """Bulk-insert extracted items. items = list of dicts."""
    import json
    if not items:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        for item in items:
            await conn.execute(
                f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                    (inbound_log_id, customer_id, plan_id, item_type,
                     placeholder_key, task_id, extracted_value, confidence, reasoning, status)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                item["inbound_log_id"], item["customer_id"], item.get("plan_id"),
                item["item_type"],
                item.get("placeholder_key"), item.get("task_id"),
                item.get("extracted_value"), item.get("confidence"), item.get("reasoning"),
                item.get("status", "pending"),
            )


async def apply_answer(customer_id: int, plan_id: str, placeholder_key: str, value: str,
                       extraction_item_id: str, confidence: float = 0.0,
                       reasoning: str = "") -> int:
    """Write answer to customer_profile_data + update task status + mark item applied.

    Returns the number of customer_tasks rows actually updated (0 = key not found / cancelled).

    Order matters:
      1. Upsert profile_data
      2. Update task FIRST (set answered_via / answer) — before updating placeholder
      3. Update placeholder → triggers sync_task_from_placeholder which sets status='completed'
         Task already has answered_via/answer filled in at this point.
      4. Mark extraction item applied
    """
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Upsert profile data
        await conn.execute(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_profile_data
                (customer_id, field_key, field_value, source, verified, confidence,
                 filled_via, filled_at)
                VALUES ($1,$2,$3,'email',false,90,'email',NOW())
                ON CONFLICT (customer_id, field_key) DO UPDATE SET
                    field_value = EXCLUDED.field_value, source='email',
                    filled_via='email', filled_at=NOW(), updated_at=NOW()""",
            customer_id, placeholder_key, value,
        )
        # 2. Update task BEFORE updating placeholder (so the trigger sees answered_via/answer)
        #    - If pending: transition to 'answered'
        #    - If already answered/completed: keep status, just refresh answer (overwrite)
        #    - Never touch cancelled tasks
        # First check current status so we can log overwrites clearly
        existing = await conn.fetchrow(
            f"SELECT status, answer FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks "
            f"WHERE customer_id = $1 AND placeholder_key = $2 AND status != 'cancelled' LIMIT 1",
            customer_id, placeholder_key,
        )
        task_result = await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET answer                = $3,
                    answered_via          = COALESCE(answered_via, 'email'),
                    answered_at           = COALESCE(answered_at, NOW()),
                    extraction_confidence = $4,
                    extraction_reasoning  = $5,
                    updated_at            = NOW(),
                    status = CASE
                        WHEN status = 'pending' THEN 'answered'
                        ELSE status
                    END
                WHERE customer_id = $1 AND placeholder_key = $2
                  AND status != 'cancelled'""",
            customer_id, placeholder_key, value, confidence, reasoning or None,
        )
        tasks_updated = int(task_result.split()[-1]) if task_result else 0
        if tasks_updated == 0:
            logger.warning(
                f"apply_answer: key={placeholder_key!r} matched 0 tasks for "
                f"customer={customer_id} — key not in customer_tasks or task is cancelled"
            )
        elif existing and existing["status"] in ("answered", "completed"):
            old_val = (existing["answer"] or "")[:60]
            new_val = (value or "")[:60]
            if old_val != new_val:
                logger.info(
                    f"apply_answer: key={placeholder_key!r} OVERWRITTEN for customer={customer_id} "
                    f"(was {existing['status']!r}) — old={old_val!r} → new={new_val!r}"
                )
            else:
                logger.info(
                    f"apply_answer: key={placeholder_key!r} CONFIRMED (same value) for customer={customer_id} "
                    f"(status={existing['status']!r})"
                )
        else:
            logger.info(f"apply_answer: key={placeholder_key!r} → {tasks_updated} task(s) updated for customer={customer_id}")

        # 3. Update placeholder status → triggers trg_placeholder_to_task which
        #    sets task.status = 'completed' (task already has answered_via/answer set above)
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                SET status = 'collected', updated_at = NOW()
                WHERE customer_id = $1 AND placeholder_key = $2
                  AND ($3::uuid IS NULL OR plan_id = $3)""",
            customer_id, placeholder_key, plan_id,
        )
        # 4. Mark extraction item applied
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                SET status = 'auto_applied', applied_at = NOW()
                WHERE id = $1""",
            extraction_item_id,
        )
    return tasks_updated


async def apply_evidence_match(
    task_id: str, customer_id: int, inbound_log_id: str,
    filename: str, storage_path: str, confidence: float,
    extraction_item_id: str, reasoning: str = "",
) -> bool:
    """Copy attachment from email storage to customer evidence dir, mark task answered.

    Returns True if the source file was found and copied, False if file was missing
    (DB update still proceeds so the task is marked answered regardless).
    """
    import shutil
    import json as _json
    from pathlib import Path
    from datetime import datetime

    src = Path(storage_path)
    dest_dir = Path(f"/app/storage/customers/{customer_id}/evidence/{task_id}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    file_copied = False
    if src.exists():
        shutil.copy2(src, dest)
        file_copied = True

    file_entry = _json.dumps([{
        "filename": filename,
        "path": str(dest),
        "source": "email",
        "confidence": confidence,
        "reasoning": reasoning or None,
        "uploaded_at": datetime.utcnow().isoformat(),
    }])

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET evidence_uploaded = TRUE,
                    evidence_files = COALESCE(evidence_files, '[]'::jsonb) || $2::jsonb,
                    status = 'completed',
                    answered_via = COALESCE(answered_via, 'email'),
                    answered_at  = COALESCE(answered_at, NOW()),
                    extraction_confidence = $3,
                    extraction_reasoning  = $4,
                    updated_at   = NOW()
                WHERE id = $1::uuid AND status != 'cancelled'""",
            task_id, file_entry, confidence, reasoning or None,
        )
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                SET status = 'auto_applied', applied_at = NOW()
                WHERE id = $1""",
            extraction_item_id,
        )
    return file_copied


def _parse_jsonb(val):
    """Parse asyncpg JSONB field (returned as string) to Python object."""
    import json as _json
    if isinstance(val, str):
        try:
            return _json.loads(val)
        except Exception:
            return {}
    return val if val is not None else {}


async def mark_tasks_human_review(customer_id: int, reason: str) -> int:
    """Mark all pending tasks for this customer as needs_human_review=TRUE.
    Returns the number of rows updated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET needs_human_review = TRUE, human_review_reason = $2, updated_at = NOW()
                WHERE customer_id = $1
                  AND status = 'pending'
                  AND (needs_human_review = FALSE OR needs_human_review IS NULL)""",
            customer_id, reason,
        )
    count = int(result.split()[-1]) if result else 0
    logger.info(f"mark_tasks_human_review: customer={customer_id}, flagged={count} tasks, reason={reason!r}")
    return count


async def count_consecutive_zero_extractions(customer_id: int) -> int:
    """Count how many consecutive most-recent inbound emails for this customer had 0 answers extracted."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT extraction_result FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log
                WHERE customer_id = $1
                  AND extraction_result IS NOT NULL
                ORDER BY received_at DESC
                LIMIT 5""",
            customer_id,
        )
    count = 0
    for r in rows:
        result = _parse_jsonb(r["extraction_result"])
        if len(result.get("answers", [])) == 0:
            count += 1
        else:
            break
    return count


async def get_extraction_prompts() -> dict:
    """Fetch email extraction prompts from ai_prompts table.
    Returns dict with 'system' and 'user' keys, falling back to None if not found."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT prompt_key, prompt_text
                FROM {settings.DATABASE_APP_SCHEMA}.ai_prompts
                WHERE prompt_key IN ('email_extraction_system', 'email_extraction_user')
                  AND is_active = TRUE""",
        )
    result = {}
    for row in rows:
        if row["prompt_key"] == "email_extraction_system":
            result["system"] = row["prompt_text"]
        elif row["prompt_key"] == "email_extraction_user":
            result["user"] = row["prompt_text"]
    return result


async def get_ai_config_for_service(service_name: str) -> dict:
    """Get AI provider/model/api_key for a given service from ai_config + llm_providers."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        ai_row = await conn.fetchrow(
            f"SELECT provider, model FROM {settings.DATABASE_APP_SCHEMA}.ai_config WHERE service = $1",
            service_name,
        )
    provider = (ai_row["provider"] if ai_row else None) or "gemini"
    model    = (ai_row["model"]    if ai_row else None) or "gemini-2.5-flash"

    async with pool.acquire() as conn:
        prow = await conn.fetchrow(
            f"SELECT api_key FROM {settings.DATABASE_APP_SCHEMA}.llm_providers"
            f" WHERE name = $1 AND enabled = true",
            provider,
        )
    api_key = _decrypt_credential(prow["api_key"] or "") if prow and prow["api_key"] else ""
    return {"provider": provider, "model": model, "_api_key": api_key}


async def get_iso_standard_with_placeholders(iso_standard_id: str) -> dict | None:
    """Return ISO standard row with parsed placeholder_dictionary."""
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
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
            result["placeholder_dictionary"] = _json.loads(raw)
        except Exception:
            result["placeholder_dictionary"] = []
    return result


async def get_iso360_template_by_key(placeholder_key: str) -> dict | None:
    """Return existing iso360_template for a placeholder_key, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
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
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.iso360_templates
                (placeholder_key, type, update_frequency, title, responsible_role, steps, evidence_fields)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                RETURNING id""",
            placeholder_key, type_, update_frequency, title, responsible_role,
            _json.dumps(steps), _json.dumps(evidence_fields),
        )
    return str(row["id"])


async def link_iso360_template_to_standard(
    template_id: str, iso_standard_id: str, covered_clauses: list | None = None,
) -> None:
    """Insert into iso360_template_iso_mapping (idempotent — ON CONFLICT DO NOTHING)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.iso360_template_iso_mapping
                (template_id, iso_standard_id, covered_clauses)
                VALUES ($1, $2, $3)
                ON CONFLICT (template_id, iso_standard_id) DO NOTHING""",
            template_id, iso_standard_id, covered_clauses or [],
        )


async def get_iso_recurring_activities(iso_standard_id: str) -> list:
    """
    Collect all recurring activities for an ISO standard from two sources:
      1. recurring_activities JSONB on each linked catalog template (per-template activities)
      2. iso360_recurring_activities JSONB on the iso_standards row (cross-cutting)
    Returns a merged, deduplicated list by 'key', each entry enriched with
    'template_name' and 'template_id' (None for cross-cutting entries).
    Returns empty list if no recurring_activities have been populated yet
    (standard needs to be rebuilt after migration 024).
    """
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
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


async def get_plans_needing_iso360_adjustment() -> list:
    """Return plans where iso360_enabled=TRUE, adjustment_pass_done=FALSE,
    and onboarding progress >= onboarding_threshold_pct.
    Returns [{plan_id, customer_id, iso_standard, iso_standard_id,
              onboarding_threshold_pct, reminder_month, reminder_day}].
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                p.id AS plan_id,
                p.customer_id,
                iso.code AS iso_standard,
                iso.id   AS iso_standard_id,
                s.onboarding_threshold_pct,
                s.reminder_month,
                s.reminder_day
            FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
            JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = p.iso_standard_id
            JOIN {settings.DATABASE_APP_SCHEMA}.iso360_plan_settings s ON s.plan_id = p.id
            WHERE p.iso360_enabled = TRUE
              AND s.adjustment_pass_done = FALSE
              AND (
                  SELECT CASE
                      WHEN COUNT(*) FILTER (
                          WHERE status NOT IN ('cancelled')
                            AND (is_ignored = false OR is_ignored IS NULL)
                      ) = 0 THEN 0
                      ELSE ROUND(
                          COUNT(*) FILTER (
                              WHERE status IN ('answered', 'completed')
                                AND (is_ignored = false OR is_ignored IS NULL)
                          )::NUMERIC
                          / COUNT(*) FILTER (
                              WHERE status NOT IN ('cancelled')
                                AND (is_ignored = false OR is_ignored IS NULL)
                          )::NUMERIC * 100
                      )
                  END
                  FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                  WHERE ct.plan_id = p.id
              ) >= s.onboarding_threshold_pct
            """,
        )
    return [dict(r) for r in rows]


async def get_customer_answers_context(customer_id: int, plan_id: str) -> str:
    """Return a formatted string of all answered/completed tasks for LLM context."""
    pool = await get_pool()
    async with pool.acquire() as conn:
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
    pool = await get_pool()
    async with pool.acquire() as conn:
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
    import json as _json
    pool = await get_pool()
    template_id = str(template["id"])
    async with pool.acquire() as conn:
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
            _json.dumps(personalized_content),
            next_due_date,
        )
    return str(row["id"])


async def mark_adjustment_pass_done(plan_id: str) -> None:
    """Set adjustment_pass_done=TRUE in iso360_plan_settings for this plan."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.iso360_plan_settings
                SET adjustment_pass_done = TRUE, updated_at = NOW()
                WHERE plan_id = $1::uuid""",
            plan_id,
        )


async def get_iso360_templates_for_standard(iso_standard_id: str) -> list:
    """Return all iso360_templates linked to the given ISO standard, with parsed JSONB."""
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
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
        d["steps"]          = _json.loads(d["steps"])          if isinstance(d.get("steps"), str)          else (d.get("steps") or [])
        d["evidence_fields"] = _json.loads(d["evidence_fields"]) if isinstance(d.get("evidence_fields"), str) else (d.get("evidence_fields") or [])
        result.append(d)
    return result


async def create_notification(
    type: str, severity: str, title: str, message: str,
    customer_id: int | None = None, customer_name: str | None = None,
) -> str:
    """Insert a notification row visible to all dashboard users."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.notifications
                (type, severity, title, message, customer_id, customer_name, created_by_name)
                VALUES ($1, $2, $3, $4, $5, $6, 'System')
                RETURNING id""",
            type, severity, title, message, customer_id, customer_name,
        )
    return str(row["id"])
