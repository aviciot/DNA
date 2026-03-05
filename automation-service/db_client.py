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
    """Load automation config + resolve LLM key from central llm_providers table."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.automation_config WHERE id = 1"
        )
    if not row:
        return {}
    cfg = dict(row)
    for field in ("gmail_app_password", "sendgrid_api_key"):
        if cfg.get(field):
            cfg[field] = _decrypt_credential(cfg[field])

    # Resolve API key from central llm_providers table
    provider = cfg.get("extraction_provider") or "gemini"
    async with pool.acquire() as conn:
        prow = await conn.fetchrow(
            f"SELECT api_key, model FROM {settings.DATABASE_APP_SCHEMA}.llm_providers"
            f" WHERE name = $1 AND enabled = true",
            provider,
        )
    if prow:
        cfg["_api_key"] = _decrypt_credential(prow["api_key"] or "")
        if not cfg.get("extraction_model"):
            cfg["extraction_model"] = prow["model"]

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
                ORDER BY ct.priority DESC, ct.created_at""",
            customer_id, plan_id,
        )
    return [dict(r) for r in rows]


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
