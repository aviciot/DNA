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
from db_client import get_pool, get_automation_config, get_customer_automation_config, get_collection_request_by_short_code

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
                f"""SELECT ecr.*, c.name AS customer_name,
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
                    ORDER BY ecr.sent_at""",
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
