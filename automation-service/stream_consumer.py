"""
Automation Stream Consumer
===========================
Reads from Redis streams:
  automation:send     — send a collection campaign email
  automation:extract  — extract answers from an inbound email
"""
import asyncio
import json
import logging
import os
import traceback
import uuid
from typing import Any

import redis.asyncio as aioredis

from config import settings
from db_client import (
    get_pool, get_automation_config, get_customer_by_id,
    get_pending_tasks_for_plan, get_collection_request_by_token,
    get_customer_automation_config,
    create_collection_request, create_inbound_log, update_inbound_log_status,
    create_extraction_items, apply_answer, apply_evidence_match, create_notification,
    mark_tasks_human_review, count_consecutive_zero_extractions,
)
from email_sender import send_campaign_email, send_extraction_reply_email
from attachment_parser import parse_attachment
from agents.email_extract_agent import extract_from_email
from agents.extraction_reply_agent import draft_reply_email

logger = logging.getLogger(__name__)

STREAMS = [
    ("automation:send",         "automation-send-workers"),
    ("automation:extract",      "automation-extract-workers"),
    ("automation:imap_trigger", "automation-imap-trigger-workers"),
]


class AutomationConsumer:
    def __init__(self):
        self.consumer_id = f"auto-worker-{uuid.uuid4().hex[:6]}"
        self._redis: aioredis.Redis | None = None
        self._running = False

    async def start(self):
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        # Create consumer groups (idempotent)
        for stream, group in STREAMS:
            try:
                await self._redis.xgroup_create(stream, group, id="0", mkstream=True)
            except Exception:
                pass  # group already exists
        self._running = True
        logger.info(f"Automation consumer started: {self.consumer_id}")

    async def stop(self):
        self._running = False
        if self._redis:
            await self._redis.aclose()

    async def consume_forever(self):
        while self._running:
            try:
                for stream, group in STREAMS:
                    await self._consume_once(stream, group)
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer loop error: {e}")
                await asyncio.sleep(5)

    async def _consume_once(self, stream: str, group: str):
        try:
            messages = await self._redis.xreadgroup(
                groupname=group,
                consumername=self.consumer_id,
                streams={stream: ">"},
                count=1,
                block=1000,
            )
            if not messages:
                return
            for _, msg_list in messages:
                for msg_id, data in msg_list:
                    try:
                        # Safely parse JSON-encoded fields — only lists/objects, not plain strings
                        parsed = {}
                        for k, v in data.items():
                            if isinstance(v, str) and v.startswith(('{', '[')):
                                try:
                                    parsed[k] = json.loads(v)
                                except (json.JSONDecodeError, ValueError):
                                    parsed[k] = v
                            else:
                                parsed[k] = v
                        if stream == "automation:send":
                            await self._handle_send(parsed)
                        elif stream == "automation:extract":
                            await self._handle_extract(parsed)
                        elif stream == "automation:imap_trigger":
                            await self._handle_imap_trigger()
                        await self._redis.xack(stream, group, msg_id)
                    except Exception as e:
                        logger.error(f"Failed to process {stream} msg {msg_id}: {e}\n{traceback.format_exc()}")
        except Exception as e:
            logger.debug(f"consume {stream}: {e}")

    # ── SEND ────────────────────────────────────────────────────
    async def _handle_send(self, data: dict):
        customer_id = int(data["customer_id"])
        plan_id = data["plan_id"]
        iso_code = data.get("iso_code", "")
        iso_name = data.get("iso_name", "")
        created_by_raw = data.get("created_by")
        created_by = int(created_by_raw) if created_by_raw and str(created_by_raw).isdigit() else None
        # Redis stores all values as strings — "false" is truthy in Python, must compare explicitly
        is_followup = str(data.get("is_followup", "false")).lower() == "true"
        followup_number = int(data.get("followup_number", 1))
        parent_request_id = data.get("parent_request_id")

        # Per-customer config overrides (injected by backend when sending)
        contact_name_override = data.get("contact_name")  # None = use customer.name
        language = data.get("language", "en")
        send_to_override_raw = data.get("send_to_override")
        send_to_override = json.loads(send_to_override_raw) if send_to_override_raw else None

        cfg = await get_automation_config()
        customer = await get_customer_by_id(customer_id)
        if not customer:
            logger.error(f"Send: customer {customer_id} not found")
            return

        # Build question/evidence snapshots from pending tasks
        tasks = await get_pending_tasks_for_plan(customer_id, plan_id)
        questions = []
        evidence_tasks = []
        for t in tasks:
            if t.get("requires_evidence"):
                evidence_tasks.append({
                    "task_id": str(t["id"]),
                    "title": t["title"],
                    "description": t.get("evidence_description", ""),
                })
            elif t.get("placeholder_key"):
                questions.append({
                    "placeholder_key": t["placeholder_key"],
                    "question": t["title"],
                    "hint": t.get("description", ""),
                })

        if not questions and not evidence_tasks:
            logger.info(f"Send: no pending tasks for customer {customer_id} / plan {plan_id}")
            return

        # Determine recipient addresses: override takes priority over customer fields
        if send_to_override:
            to_addresses = [a for a in send_to_override if a]
        else:
            to_addresses = list({
                addr for addr in [
                    customer.get("compliance_email"),
                    customer.get("contact_email"),
                    customer.get("document_email"),
                    customer.get("email"),
                ] if addr
            })
        if not to_addresses:
            logger.warning(f"Send: no email address for customer {customer_id}")
            return

        customer_name = contact_name_override or customer.get("name", "")
        token = uuid.uuid4().hex[:32]
        tag = f"[DNA-{token[:8].upper()}]"
        total = len(questions) + len(evidence_tasks)

        logger.info(
            f"{tag} Send: customer={customer_id}, plan={plan_id[:8]}..., "
            f"questions={len(questions)}, evidence={len(evidence_tasks)}, to={to_addresses}"
        )

        # ── CRITICAL: create the DB record BEFORE sending the email ──────────
        # If we sent first and the DB write failed, the token would be in the
        # customer's inbox with no matching record — all replies would land as
        # orphans with questions=[] and the LLM would hallucinate placeholder keys.
        # By writing first: if the email fails we delete the record cleanly;
        # the token is never "in the wild" without a DB entry.
        placeholder_subject = (
            f"[DNA-{token[:8].upper()}] Follow-up #{followup_number}: {iso_code} — {total} items"
            if is_followup else
            f"[DNA-{token[:8].upper()}] {iso_code} — {total} items need your attention"
        )
        request_id = await create_collection_request(
            customer_id=customer_id, plan_id=plan_id, token=token,
            questions_snapshot=questions, evidence_snapshot=evidence_tasks,
            sent_to=to_addresses, subject=placeholder_subject,
            campaign_number=followup_number,
            parent_request_id=parent_request_id,
            created_by=created_by,
        )
        logger.info(f"{tag} DB record created (id={request_id[:8]}...) — sending email now")

        ok, actual_subject = await send_campaign_email(
            cfg=cfg,
            customer_name=customer_name,
            iso_code=iso_code,
            iso_name=iso_name,
            to_addresses=to_addresses,
            token=token,
            questions=questions,
            evidence_tasks=evidence_tasks,
            is_followup=is_followup,
            followup_number=followup_number,
            language=language,
        )

        if ok:
            # Update subject with localized value from email_sender
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE {settings.DATABASE_APP_SCHEMA}.email_collection_requests "
                    f"SET subject = $2 WHERE id = $1",
                    request_id, actual_subject,
                )
            logger.info(f"{tag} ✓ Campaign sent to {to_addresses} — subject: {actual_subject}")
        else:
            # Email never reached the customer — remove the record so the token
            # never exists "in the wild" without a DB entry
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests WHERE id = $1",
                    request_id,
                )
            logger.error(
                f"{tag} ✗ Email delivery failed — DB record deleted to prevent ghost token. "
                f"Customer={customer_id}, to={to_addresses}"
            )

    # ── EXTRACT ─────────────────────────────────────────────────
    async def _handle_extract(self, data: dict):
        log_id = data["log_id"]
        token = data.get("token")
        _cid_raw = data.get("customer_id")
        customer_id = int(_cid_raw) if _cid_raw and str(_cid_raw).isdigit() else None
        body_text = data.get("body_text", "")
        attachments_meta = data.get("attachments", [])  # [{filename, content_type, storage_path}]

        # Use DNA-XXXXXXXX tag (from token) for traceable log lines; fall back to log_id prefix
        tag = f"[DNA-{token[:8].upper()}]" if token else f"[LOG-{log_id[:8]}]"
        logger.info(f"{tag} Extract started: log={log_id[:8]}, customer={customer_id}")

        # Grab original subject from the inbound log for reply threading
        original_subject = data.get("subject") or ""

        cfg = await get_automation_config()

        # Resolve campaign request
        request = await get_collection_request_by_token(token) if token else None
        # asyncpg returns JSONB columns as strings — parse them if needed
        def _parse_jsonb(val):
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return []
            return val if isinstance(val, list) else []
        questions = _parse_jsonb(request.get("questions_snapshot")) if request else []
        evidence_tasks = _parse_jsonb(request.get("evidence_snapshot")) if request else []
        plan_id = str(request["plan_id"]) if request else None
        if not customer_id and request:
            customer_id = request["customer_id"]

        if not customer_id:
            await update_inbound_log_status(log_id, "skipped")
            logger.info(f"{tag} Extract: no customer found, skipping log {log_id}")
            return

        # Always load the customer's current tasks as the primary question list.
        # The campaign snapshot may be stale or cover a different subset — tasks
        # are the source of truth. Snapshot questions not already in the task list
        # are appended as supplementary context (capped at 100 total).
        if customer_id:
            pool = await get_pool()
            async with pool.acquire() as conn:
                task_rows = await conn.fetch(
                    f"""SELECT placeholder_key, title, description, plan_id, status, answer
                        FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
                        WHERE customer_id = $1
                          AND status NOT IN ('cancelled')
                          AND placeholder_key IS NOT NULL
                          AND (is_ignored = false OR is_ignored IS NULL)
                          AND (needs_human_review = FALSE OR needs_human_review IS NULL)
                        ORDER BY
                          CASE status
                            WHEN 'pending'     THEN 0
                            WHEN 'in_progress' THEN 1
                            WHEN 'answered'    THEN 2
                            ELSE 3
                          END,
                          priority DESC NULLS LAST
                        LIMIT 100""",
                    customer_id,
                )
            if task_rows:
                task_questions = [
                    {
                        "placeholder_key": r["placeholder_key"],
                        "question": r["title"],
                        "hint": r.get("description") or "",
                        "status": r["status"],
                        "current_answer": r.get("answer"),
                    }
                    for r in task_rows
                ]
                # Supplement with snapshot questions not covered by current tasks
                task_keys = {q["placeholder_key"] for q in task_questions}
                extra = [q for q in questions if q.get("placeholder_key") not in task_keys]
                questions = task_questions + extra[:max(0, 100 - len(task_questions))]
                # Infer plan_id from tasks if not already set by campaign
                if plan_id is None:
                    from collections import Counter
                    plan_ids = [str(r["plan_id"]) for r in task_rows if r["plan_id"]]
                    if plan_ids:
                        most_common_plan, _ = Counter(plan_ids).most_common(1)[0]
                        plan_id = most_common_plan
                logger.info(
                    f"{tag} loaded {len(task_questions)} customer tasks "
                    f"+ {len(extra)} snapshot extras = {len(questions)} total questions"
                )
            else:
                logger.info(f"{tag} no pending tasks found for customer {customer_id}")

        await update_inbound_log_status(log_id, "processing")

        # Parse attachments (guard against malformed items)
        if not isinstance(attachments_meta, list):
            attachments_meta = []
        parsed_attachments = []
        for att in attachments_meta:
            if not isinstance(att, dict):
                continue
            if att.get("storage_path") and os.path.exists(att["storage_path"]):
                parsed = parse_attachment(att["storage_path"], att.get("content_type", ""), att.get("filename", ""))
                parsed_attachments.append(parsed)

        # Call LLM extraction
        result = await extract_from_email(
            cfg=cfg,
            questions=questions,
            evidence_tasks=evidence_tasks,
            body_text=body_text,
            parsed_attachments=parsed_attachments,
            settings=settings,
        )

        await update_inbound_log_status(log_id, "extracted", extraction_result=result)

        # Build extraction items
        auto_apply_threshold = float(cfg.get("auto_apply_threshold") or 0.85)
        confidence_floor = float(cfg.get("confidence_floor") or 0.60)
        review_mode = cfg.get("review_mode") or "hybrid"

        items_to_insert = []
        for ans in result.get("answers", []):
            confidence = float(ans.get("confidence") or 0)
            if confidence < confidence_floor:
                continue
            # Determine status
            if review_mode == "human_first":
                status = "pending"
            elif review_mode == "autonomous" or confidence >= auto_apply_threshold:
                status = "auto_applied"
            else:
                status = "pending"  # queue for review

            items_to_insert.append({
                "inbound_log_id": log_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
                "item_type": "answer",
                "placeholder_key": ans.get("placeholder_key"),
                "extracted_value": ans.get("value"),
                "confidence": confidence,
                "reasoning": ans.get("reasoning"),
                "status": status,
            })

        for ev in result.get("evidence_matches", []):
            confidence = float(ev.get("confidence") or 0)
            if confidence < confidence_floor:
                continue
            ev_status = "auto_applied" if confidence >= auto_apply_threshold else "pending"
            items_to_insert.append({
                "inbound_log_id": log_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
                "item_type": "evidence",
                "task_id": ev.get("task_id"),
                "extracted_value": ev.get("filename"),
                "confidence": confidence,
                "reasoning": ev.get("reasoning"),
                "status": ev_status,
            })

        # Log what the LLM extracted before applying
        extracted_keys = [i["placeholder_key"] for i in items_to_insert if i["item_type"] == "answer"]
        logger.info(
            f"{tag} {len(items_to_insert)} item(s) above confidence floor "
            f"(plan_id={plan_id}), keys={extracted_keys}"
        )

        await create_extraction_items(items_to_insert)

        # Auto-apply qualified answers
        auto_applied = 0    # tasks actually updated in DB
        skipped_keys = []
        pool = await get_pool()
        for item in items_to_insert:
            if item["status"] == "auto_applied" and item["item_type"] == "answer":
                # get the item id we just inserted
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        f"""SELECT id FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                            WHERE inbound_log_id=$1 AND placeholder_key=$2 LIMIT 1""",
                        log_id, item["placeholder_key"],
                    )
                if row:
                    tasks_updated = await apply_answer(
                        customer_id=customer_id, plan_id=plan_id,
                        placeholder_key=item["placeholder_key"],
                        value=item["extracted_value"],
                        extraction_item_id=str(row["id"]),
                        confidence=item["confidence"],
                        reasoning=item.get("reasoning") or "",
                    )
                    if tasks_updated > 0:
                        auto_applied += tasks_updated
                    else:
                        skipped_keys.append(item["placeholder_key"])

        # Auto-apply high-confidence evidence matches
        for item in items_to_insert:
            if item["status"] == "auto_applied" and item["item_type"] == "evidence":
                task_id = item.get("task_id")
                filename = item.get("extracted_value", "")
                if not task_id or not filename:
                    continue
                # Look up the extraction item ID we just inserted
                async with pool.acquire() as conn:
                    ev_row = await conn.fetchrow(
                        f"""SELECT id FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                            WHERE inbound_log_id=$1 AND task_id=$2::uuid
                              AND item_type='evidence' LIMIT 1""",
                        log_id, task_id,
                    )
                if not ev_row:
                    continue
                # Look up storage_path from original attachments_meta by filename
                att_meta = next(
                    (a for a in attachments_meta if isinstance(a, dict) and a.get("filename") == filename),
                    {},
                )
                copied = await apply_evidence_match(
                    task_id=task_id,
                    customer_id=customer_id,
                    inbound_log_id=log_id,
                    filename=filename,
                    storage_path=att_meta.get("storage_path", ""),
                    confidence=item["confidence"],
                    extraction_item_id=str(ev_row["id"]),
                    reasoning=item.get("reasoning") or "",
                )
                logger.info(
                    f"{tag} evidence auto-applied: task={task_id[:8]}, "
                    f"file={filename!r}, copied={copied}"
                )
                auto_applied += 1

        pending_review = sum(1 for i in items_to_insert if i["status"] == "pending")
        if skipped_keys:
            logger.warning(
                f"{tag} {len(skipped_keys)} key(s) matched no task "
                f"(hallucinated or already completed): {skipped_keys}"
            )
        logger.info(f"{tag} ✓ Extract complete: tasks_updated={auto_applied}, pending_review={pending_review}")
        await update_inbound_log_status(log_id, "applied")

        # ── Reply email ────────────────────────────────────────────────────────
        if cfg.get("send_extraction_reply", True):
            try:
                cfg_customer = await get_customer_automation_config(customer_id)
                cfg_customer = cfg_customer or {}
                customer_rec_for_reply = await get_customer_by_id(customer_id)
                customer_name_for_reply = (customer_rec_for_reply or {}).get("name", "")

                auto_threshold = float(cfg.get("auto_apply_threshold") or 0.85)
                applied_items = [a for a in result.get("answers", []) if float(a.get("confidence", 0)) >= auto_threshold]
                review_items_list = [a for a in result.get("answers", []) if float(a.get("confidence", 0)) < auto_threshold]
                unmatched_keys = result.get("follow_up_keys", [])

                lang = cfg_customer.get("preferred_language") or "en"
                to_emails_reply: list[str] = []
                if cfg_customer.get("send_to_emails"):
                    to_emails_reply = list(cfg_customer["send_to_emails"])
                elif customer_rec_for_reply:
                    to_emails_reply = list({
                        addr for addr in [
                            customer_rec_for_reply.get("compliance_email"),
                            customer_rec_for_reply.get("contact_email"),
                            customer_rec_for_reply.get("email"),
                        ] if addr
                    })

                if to_emails_reply:
                    llm_content = await draft_reply_email(
                        cfg=cfg,
                        applied=applied_items,
                        needs_review=review_items_list,
                        unmatched=unmatched_keys,
                        language=lang,
                        settings=settings,
                    )
                    await send_extraction_reply_email(
                        cfg=cfg,
                        to_emails=to_emails_reply,
                        customer_name=customer_name_for_reply,
                        language=lang,
                        llm_content=llm_content,
                        applied_count=len(applied_items),
                        review_count=len(review_items_list),
                        subject_ref=original_subject,
                    )
                else:
                    logger.info(f"{tag} Reply skipped: no recipient emails for customer {customer_id}")
            except Exception as _re:
                logger.warning(f"{tag} Reply email failed (non-fatal): {_re}")

        # ── Consecutive-zero check → flag tasks ────────────────────────────────
        if len(result.get("answers", [])) == 0:
            try:
                consec = await count_consecutive_zero_extractions(customer_id)
                if consec >= 2:
                    flagged = await mark_tasks_human_review(
                        customer_id,
                        f"No answers extracted from {consec} consecutive emails",
                    )
                    logger.info(f"{tag} needs_human_review set on {flagged} task(s) for customer {customer_id} ({consec} consecutive zero-extraction emails)")
            except Exception as _ze:
                logger.warning(f"{tag} Consecutive-zero check failed (non-fatal): {_ze}")

        # Notify dashboard — always fires regardless of extraction outcome
        try:
            customer_rec = await get_customer_by_id(customer_id)
            customer_name = (customer_rec or {}).get("name") or (customer_rec or {}).get("company_name")
            label = customer_name or f"customer {customer_id}"
            if auto_applied > 0 and pending_review > 0:
                severity = "warning"
                title = f"Email from {label} — partial extraction"
                message = f"{auto_applied} answer(s) applied automatically, {pending_review} need review."
            elif auto_applied > 0:
                severity = "info"
                title = f"Email from {label} — answers applied"
                message = f"{auto_applied} answer(s) applied automatically."
            elif pending_review > 0:
                severity = "warning"
                title = f"Email from {label} — review needed"
                message = f"{pending_review} extracted answer(s) are waiting for your review."
            else:
                severity = "info"
                title = f"Email received from {label}"
                message = "No matching answers found in this email."
            notif_id = await create_notification(
                type="email_extraction", severity=severity,
                title=title, message=message,
                customer_id=customer_id, customer_name=customer_name,
            )
            await self._redis.publish("notifications:new", json.dumps({
                "id": notif_id, "type": "email_extraction", "severity": severity,
                "title": title, "message": message,
                "customer_id": customer_id, "customer_name": customer_name,
                "created_by_name": "System",
            }))
        except Exception as _ne:
            logger.warning(f"{tag} notification dispatch failed: {_ne}")

    # ── MANUAL IMAP TRIGGER ─────────────────────────────────────
    async def _handle_imap_trigger(self):
        """Called when POST /trigger-imap-poll is hit. Runs one IMAP poll immediately."""
        from scheduler import scheduler
        cfg = await get_automation_config()
        if not cfg.get("enabled"):
            logger.info("IMAP trigger: automation disabled, skipping")
            return
        logger.info("IMAP poll triggered manually")
        await scheduler._poll_imap_job()


consumer = AutomationConsumer()
