"""
Automation Scheduler
====================
APScheduler jobs:
  - IMAP poll (every N seconds)
  - Follow-up campaigns (daily)
  - Expire stale requests (daily)
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

import pytz
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from db_client import (
    get_pool, get_automation_config, get_customer_automation_config,
    get_collection_request_by_short_code,
    get_pending_notification_tasks, get_ai_prompt,
    complete_notification_task, fail_notification_task,
    get_plans_needing_iso360_adjustment,
    get_iso360_due_activities, create_iso360_scheduled_task,
)

logger = logging.getLogger(__name__)


class AutomationScheduler:
    def __init__(self, listener=None):
        self._scheduler = AsyncIOScheduler()
        self._listener = listener  # IMAPListener instance
        self._redis: aioredis.Redis | None = None

    async def start(self, redis_url: str):
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

        # Jobs added dynamically so they pick up latest config from DB
        self._scheduler.add_job(
            self._poll_imap_job, "interval", seconds=60, id="imap_poll",
            replace_existing=True, misfire_grace_time=30,
        )
        self._scheduler.add_job(
            self._followup_job, "cron", hour=9, minute=0, id="daily_followup",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._expire_stale_job, "cron", hour=8, minute=30, id="expire_stale",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._notification_job, "interval", minutes=5, id="notification_sender",
            replace_existing=True, misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._iso360_annual_job, "cron", hour=7, minute=0, id="iso360_annual",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._iso360_adjustment_check_job, "interval", hours=6,
            id="iso360_adjustment_check", replace_existing=True,
            misfire_grace_time=300,
        )
        self._scheduler.add_job(
            self._iso360_scheduled_tasks_job, "cron", hour=8, minute=15,
            id="iso360_scheduled_tasks", replace_existing=True,
            misfire_grace_time=1800,
        )
        self._scheduler.start()
        logger.info("Automation scheduler started")

    def stop(self):
        self._scheduler.shutdown(wait=False)

    # ── IMAP poll ────────────────────────────────────────────────
    async def _poll_imap_job(self):
        cfg = await get_automation_config()
        if not cfg.get("enabled"):
            return
        if not self._listener:
            return
        interval = int(cfg.get("imap_poll_interval_seconds") or 60)
        # Reschedule if interval changed
        job = self._scheduler.get_job("imap_poll")
        if job and job.trigger.interval.total_seconds() != interval:
            self._scheduler.reschedule_job("imap_poll", trigger="interval", seconds=interval)

        customer_storage = settings.CUSTOMER_STORAGE_PATH

        async def on_email(parsed):
            await self._on_inbound_email(parsed, cfg)

        self._listener.cfg = cfg          # refresh credentials from DB each poll
        self._listener.on_email = on_email
        await self._listener.poll_once(customer_storage)

    async def _on_inbound_email(self, parsed: dict, cfg: dict):
        """Called for each new inbound email. Saves to DB and enqueues extraction.

        Token matching priority:
          1. collect_TOKEN in email headers (Reply-To / To / Delivered-To)
          2. DNA-XXXXXXXX reference code in email body or subject
          3. Sender email address matched against customer email fields
        """
        from db_client import get_customer_by_email, get_collection_request_by_token, create_inbound_log
        import re
        token = parsed.get("token")
        from_email = parsed.get("from_email", "")

        # 1. Token from email headers (standard reply path)
        request = None
        customer_id = None
        if token:
            request = await get_collection_request_by_token(token)
            if request:
                customer_id = request["customer_id"]
                logger.info(f"Inbound: matched by header token {token[:8].upper()} → customer {customer_id}")
                # Verify customer still exists — campaign may reference a deleted customer
                from db_client import get_customer_by_id
                existing = await get_customer_by_id(customer_id)
                if not existing:
                    logger.warning(
                        f"Inbound: token {token[:8].upper()} → customer {customer_id} no longer "
                        f"exists (deleted?), will re-resolve by sender email"
                    )
                    customer_id = None
                    request = None  # don't link log to deleted customer's campaign; token still used in extract job

        # 2. Reference code DNA-XXXXXXXX in subject or body (new-thread path)
        if not request:
            search_text = (parsed.get("subject") or "") + " " + (parsed.get("body_text") or "")[:3000]
            ref_match = re.search(r'DNA[-_\s]?([A-Fa-f0-9]{8})\b', search_text)
            if ref_match:
                short_code = ref_match.group(1).lower()
                request = await get_collection_request_by_short_code(short_code)
                if request:
                    customer_id = request["customer_id"]
                    token = request["token"]  # use full token for downstream steps
                    logger.info(f"Inbound: matched by reference code DNA-{short_code.upper()} (body/subject) → customer {customer_id}")
                else:
                    logger.info(f"Inbound: reference code DNA-{short_code.upper()} found but no matching campaign")

        # 3. Sender email fallback
        if not customer_id:
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', from_email)
            sender = email_match.group(0) if email_match else ""
            if sender:
                customer = await get_customer_by_email(sender)
                if customer:
                    customer_id = customer["id"]
                    logger.info(f"Inbound: matched by sender email {sender} → customer {customer_id} (no token)")

        if not customer_id:
            logger.info(f"Inbound email from {from_email}: no customer match, skipping")
            return

        log_id = await create_inbound_log(
            collection_request_id=str(request["id"]) if request else None,
            customer_id=customer_id,
            from_email=from_email,
            subject=parsed.get("subject", ""),
            body_text=parsed.get("body_text", ""),
            body_html=parsed.get("body_html", ""),
            attachments=[],
        )

        # Save attachments now — only for known customers, directly into the real log dir
        attachments = []
        raw_msg = parsed.get("_msg")
        if raw_msg is not None:
            from email_listener import _get_attachments
            attachments = _get_attachments(raw_msg, settings.CUSTOMER_STORAGE_PATH, log_id)
            if attachments:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"UPDATE {settings.DATABASE_APP_SCHEMA}.email_inbound_log"
                        f" SET attachments = $2::jsonb WHERE id = $1",
                        log_id, json.dumps(attachments),
                    )

        # Push to extraction queue
        await self._redis.xadd("automation:extract", {
            "log_id": log_id,
            "token": token or "",
            "customer_id": str(customer_id),
            "body_text": (parsed.get("body_text") or "")[:10000],
            "attachments": json.dumps(attachments),
        })
        logger.info(f"Queued extraction for log {log_id} (customer {customer_id})")

    # ── Follow-up campaigns ──────────────────────────────────────
    async def _followup_job(self):
        cfg = await get_automation_config()
        if not cfg.get("enabled"):
            return

        delay_days = int(cfg.get("followup_delay_days") or 2)
        max_followups = int(cfg.get("max_followups") or 3)

        pool = await get_pool()
        async with pool.acquire() as conn:
            # JOIN to customer_automation_config so we can filter disabled customers
            # and pass per-customer overrides to the Redis message
            stale = await conn.fetch(
                f"""SELECT DISTINCT ON (ecr.customer_id, ecr.plan_id)
                           ecr.*, c.name AS customer_name,
                           iso.code AS iso_code, iso.name AS iso_name,
                           COALESCE(cac.enabled, TRUE) AS customer_enabled,
                           cac.contact_name AS customer_contact_name,
                           cac.preferred_language AS customer_language,
                           cac.send_to_emails AS customer_send_to_emails,
                           COALESCE(cac.max_followups, {max_followups}) AS effective_max_followups,
                           COALESCE(cac.followup_delay_days, {delay_days}) AS effective_delay_days
                    FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests ecr
                    JOIN {settings.DATABASE_APP_SCHEMA}.customers c ON c.id = ecr.customer_id
                    LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans cip ON cip.id = ecr.plan_id
                    LEFT JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = cip.iso_standard_id
                    LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_automation_config cac ON cac.customer_id = ecr.customer_id
                    WHERE ecr.status = 'pending'
                      AND COALESCE(cac.enabled, TRUE) = TRUE
                      AND ecr.sent_at < NOW() - make_interval(days => COALESCE(cac.followup_delay_days, {delay_days}))
                      AND ecr.campaign_number < COALESCE(cac.max_followups, {max_followups})
                      AND ecr.expires_at > NOW()
                    ORDER BY ecr.customer_id, ecr.plan_id, ecr.sent_at DESC""",
            )

        for row in stale:
            logger.info(f"Follow-up: customer {row['customer_id']}, plan {row['plan_id']}, "
                        f"campaign #{row['campaign_number']+1}")
            msg = {
                "customer_id": str(row["customer_id"]),
                "plan_id": str(row["plan_id"]),
                "iso_code": row["iso_code"] or "",
                "iso_name": row["iso_name"] or "",
                "is_followup": "true",
                "followup_number": str(row["campaign_number"] + 1),
                "parent_request_id": str(row["id"]),
            }
            # Inject per-customer overrides
            if row.get("customer_contact_name"):
                msg["contact_name"] = row["customer_contact_name"]
            if row.get("customer_language"):
                msg["language"] = row["customer_language"]
            if row.get("customer_send_to_emails"):
                import json
                msg["send_to_override"] = json.dumps(list(row["customer_send_to_emails"]))
            await self._redis.xadd("automation:send", msg)

    # ── Notification sender (every 5 min) ────────────────────────
    async def _notification_job(self):
        """Process pending notification tasks — welcome, announcement, iso360_reminder."""
        from agents.notification_email_agent import generate_notification_email
        from email_sender import send_notification_email

        tasks = await get_pending_notification_tasks(limit=20)
        if not tasks:
            return

        cfg = await get_automation_config()
        logger.info(f"Notification job: {len(tasks)} pending task(s)")

        for task in tasks:
            task_id       = str(task["id"])
            customer_name = task.get("customer_name") or "Valued Customer"
            portal_token  = task.get("portal_token")
            portal_url    = f"{settings.PORTAL_URL}/auth?token={portal_token}" if portal_token and settings.PORTAL_URL else ""
            notification_type = task.get("notes") or "welcome_customer"  # notes stores the type
            language      = "en"  # TODO: from customer_automation_config

            # Recipient: prefer compliance_email → contact_email → email
            to_addr = (
                task.get("compliance_email") or
                task.get("contact_email") or
                task.get("customer_email")
            )
            if not to_addr:
                logger.warning(f"Notification {task_id}: no email address for customer {task['customer_id']}, skipping")
                await fail_notification_task(task_id, "No email address found for customer")
                continue

            # Build variables for LLM prompt
            variables = {
                "customer_name": customer_name,
                "portal_url": portal_url,
                "consultant_name": "The DNA Team",
            }
            # Merge plan-specific variables from task metadata if present
            if task.get("description"):
                try:
                    import json
                    extra = json.loads(task["description"])
                    if isinstance(extra, dict):
                        variables.update(extra)
                except Exception:
                    pass

            try:
                sections = await generate_notification_email(
                    notification_type=notification_type,
                    variables=variables,
                    cfg=cfg,
                    settings=settings,
                    ai_prompt_getter=get_ai_prompt,
                )
                subject = sections.pop("subject", "A message from DNA")
                ok = await send_notification_email(
                    cfg=cfg,
                    to_address=to_addr,
                    subject=subject,
                    sections=sections,
                    language=language,
                    portal_url=portal_url,
                    iso_code=variables.get("iso_code", ""),
                    iso_name=variables.get("iso_name", ""),
                )
                if ok:
                    await complete_notification_task(
                        task_id, to_addr,
                        metadata={"notification_type": notification_type, "model": cfg.get("llm_model")},
                    )
                    logger.info(f"Notification {task_id} ({notification_type}) sent to {to_addr}")
                    # ── Log LLM usage (system cost, no customer_id) ────────────────────────
                    try:
                        _notif_provider = (cfg.get("llm_provider") or "gemini").lower()
                        _notif_model    = cfg.get("llm_model") or "gemini-2.5-flash"
                        pool_log = await get_pool()
                        async with pool_log.acquire() as conn:
                            await conn.execute(
                                f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_usage_log
                                    (operation_type, provider, model, tokens_input, tokens_output,
                                     cost_usd, duration_ms, status, started_at, completed_at)
                                    VALUES ('notification_email', $1, $2, 0, 0, 0, 0, 'success', NOW(), NOW())""",
                                _notif_provider, _notif_model,
                            )
                    except Exception as _ue:
                        logger.warning(f"Notification {task_id} ai_usage_log write failed (non-fatal): {_ue}")
                else:
                    await fail_notification_task(task_id, "SMTP send returned False", to_addr)
            except Exception as e:
                logger.error(f"Notification {task_id} failed: {e}")
                await fail_notification_task(task_id, str(e), to_addr)

    # ── ISO360 Annual Reminder ────────────────────────────────────
    async def _iso360_annual_job(self):
        """Daily job: create annual review tasks for ISO360 plans whose reminder day is today.

        Logic:
          1. Find plans where iso360_enabled=TRUE AND annual_month/day match today
          2. Skip if a source_year-matching iso360_annual task already exists this year
          3. Create evidence task group (task_type='iso360_annual', requires_followup=FALSE initially)
          4. Create a notification task so customer gets an annual reminder email
          5. After 14 days, escalation flips requires_followup=TRUE (handled next daily run)
        """
        import json
        from datetime import date

        today = datetime.now(pytz.UTC)
        today_month = today.month
        today_day = today.day
        current_year = today.year

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Plans due for annual reminder today
            plans = await conn.fetch(
                f"""SELECT p.id, p.customer_id, p.iso360_activated_at,
                           p.iso360_annual_month, p.iso360_annual_day,
                           iso.code AS iso_code, iso.name AS iso_name,
                           iso.required_documents,
                           c.name AS customer_name
                    FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p
                    JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = p.iso_standard_id
                    JOIN {settings.DATABASE_APP_SCHEMA}.customers c ON c.id = p.customer_id
                    WHERE p.iso360_enabled = TRUE
                      AND p.iso360_annual_month = $1
                      AND p.iso360_annual_day = $2""",
                today_month, today_day,
            )

        for plan in plans:
            plan_id = str(plan["id"])
            customer_id = plan["customer_id"]

            # Check if annual tasks already created this year
            async with pool.acquire() as conn:
                existing = await conn.fetchval(
                    f"""SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
                        WHERE plan_id = $1 AND source = 'iso360_annual' AND source_year = $2""",
                    plan["id"], current_year,
                )
            if existing:
                logger.debug(f"ISO360 annual: plan {plan_id} already has {current_year} tasks, skipping")
                continue

            logger.info(f"ISO360 annual: creating review tasks for plan {plan_id} ({plan['iso_code']}, customer {customer_id})")

            # Parse required documents
            raw = plan["required_documents"]
            required_docs = json.loads(raw) if isinstance(raw, str) else (raw or [])

            async with pool.acquire() as conn:
                # Create one evidence task per mandatory document
                for doc in required_docs:
                    if not doc.get("mandatory"):
                        continue
                    await conn.execute(
                        f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks
                            (customer_id, plan_id, task_type, task_scope, title, description,
                             requires_followup, source, source_year, status, priority)
                            VALUES ($1, $2, 'iso360_annual', 'plan', $3, $4,
                                    FALSE, 'iso360_annual', $5, 'pending', 'high')""",
                        customer_id, plan["id"],
                        f"Annual Review {current_year}: {doc['name']}",
                        f"ISO {plan['iso_code']} clause {doc.get('clause', '')} — annual evidence update",
                        current_year,
                    )

                # Create notification task for the annual reminder email
                await conn.execute(
                    f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks
                        (customer_id, plan_id, task_type, task_scope, title,
                         requires_followup, source, source_year, status, notes, description)
                        VALUES ($1, $2, 'notification', 'plan', $3,
                                FALSE, 'iso360_annual', $4, 'pending', 'iso360_reminder', $5)""",
                    customer_id, plan["id"],
                    f"Annual ISO360 Reminder: {plan['iso_code']} {current_year}",
                    current_year,
                    json.dumps({
                        "iso_code": plan["iso_code"],
                        "iso_name": plan["iso_name"],
                        "customer_name": plan["customer_name"],
                        "review_year": current_year,
                        "mandatory_docs": len([d for d in required_docs if d.get("mandatory")]),
                    }),
                )

            logger.info(f"ISO360 annual: queued {len([d for d in required_docs if d.get('mandatory')])} review tasks + reminder email for plan {plan_id}")

        # Escalation: after 14 days flip unresolved iso360_annual tasks to requires_followup=TRUE
        async with pool.acquire() as conn:
            escalated = await conn.execute(
                f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                    SET requires_followup = TRUE
                    WHERE source = 'iso360_annual'
                      AND requires_followup = FALSE
                      AND status IN ('pending', 'in_progress')
                      AND created_at < NOW() - INTERVAL '14 days'""",
            )
        if escalated and escalated != "UPDATE 0":
            logger.info(f"ISO360 annual escalation: {escalated}")

    # ── ISO360 Adjustment check (every 6 h) ─────────────────────
    async def _iso360_adjustment_check_job(self):
        """Every 6 hours: find plans that have reached onboarding_threshold_pct
        and haven't had their customer documents personalised yet.
        Pushes one message per plan to automation:iso360_adjustment.
        """
        plans = await get_plans_needing_iso360_adjustment()
        if not plans:
            return

        logger.info(f"ISO360 adjustment check: {len(plans)} plan(s) need adjustment")
        for plan in plans:
            job_id = uuid.uuid4().hex[:12]
            await self._redis.xadd(
                "automation:iso360_adjustment",
                {
                    "job_id":            job_id,
                    "plan_id":           str(plan["plan_id"]),
                    "customer_id":       str(plan["customer_id"]),
                    "iso_standard":      plan["iso_standard"],
                    "iso_standard_id":   str(plan["iso_standard_id"]),
                    "reminder_month":    str(plan["reminder_month"] or ""),
                    "reminder_day":      str(plan["reminder_day"] or ""),
                },
            )
            logger.info(
                f"ISO360 adjustment: queued job {job_id} for "
                f"plan={str(plan['plan_id'])[:8]}, customer={plan['customer_id']}, "
                f"iso={plan['iso_standard']}"
            )

    # ── ISO360 Scheduled Tasks (daily) ───────────────────────────
    async def _iso360_scheduled_tasks_job(self):
        """Daily 08:15: find ISO360 activities due within 7 days, create customer_tasks.

        Skips:
          - event_based activities (admin-triggered only)
          - excluded activities
          - activities that already have an open task
          - activities completed in the current cycle (last_completed_at >= next_due_date)
        """
        import json as _json

        due = await get_iso360_due_activities(lookahead_days=7)
        if not due:
            logger.debug("ISO360 scheduled tasks: nothing due in next 7 days")
            return

        logger.info(f"ISO360 scheduled tasks: {len(due)} activity/activities due")
        created = 0

        for row in due:
            try:
                content = row.get("content") or {}
                if isinstance(content, str):
                    try:
                        content = _json.loads(content)
                    except Exception:
                        content = {}
                evidence_fields = content.get("evidence_fields") or []

                await create_iso360_scheduled_task(
                    doc_id=str(row["doc_id"]),
                    customer_id=row["customer_id"],
                    plan_id=str(row["plan_id"]),
                    title=row["title"],
                    iso_code=row["iso_code"],
                    iso_name=row["iso_name"],
                    customer_name=row["customer_name"],
                    placeholder_key=row["placeholder_key"],
                    responsible_role=row.get("responsible_role"),
                    evidence_fields=evidence_fields,
                    next_due_date=row["next_due_date"],
                )
                created += 1
                logger.info(
                    f"ISO360 task created: {row['placeholder_key']} "
                    f"customer={row['customer_id']} due={row['next_due_date']}"
                )
            except Exception as e:
                logger.error(
                    f"ISO360 scheduled task failed for doc {row.get('doc_id')}: {e}"
                )

        if created:
            logger.info(f"ISO360 scheduled tasks: created {created} task(s) + notification(s)")

    # ── Expire stale requests ────────────────────────────────────
    async def _expire_stale_job(self):
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_collection_requests
                    SET status = 'expired'
                    WHERE status = 'pending' AND expires_at < NOW()""",
            )
        logger.info(f"Expired stale collection requests: {result}")


scheduler = AutomationScheduler()
