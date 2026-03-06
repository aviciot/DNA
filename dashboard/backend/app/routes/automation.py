"""
Automation API Routes
=====================
GET/PUT  /api/v1/automation/config
POST     /api/v1/automation/{customer_id}/send-collection
GET      /api/v1/automation/{customer_id}/status
GET      /api/v1/automation/review-queue          (global — all customers)
GET      /api/v1/automation/{customer_id}/review-queue
POST     /api/v1/automation/review-item/{item_id}/accept
POST     /api/v1/automation/review-item/{item_id}/reject
POST     /api/v1/webhooks/email-inbound            (future SendGrid inbound parse)
"""
import asyncio
import base64
import hashlib
import imaplib
import json
import logging
import shutil
import smtplib
import ssl
import uuid
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Optional

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user, require_operator
from ..database import get_db_pool
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Credential encryption helpers
# Fernet symmetric encryption — key derived from app SECRET_KEY
# ──────────────────────────────────────────────────────────────
_SENSITIVE_FIELDS = ("gmail_app_password", "sendgrid_api_key")
_ENCRYPTED_PREFIX = "enc:"


def _get_fernet() -> Fernet:
    raw = settings.SECRET_KEY.encode()
    # Fernet needs a 32-byte URL-safe base64 key
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt_credential(value: str) -> str:
    """Encrypt a sensitive string — returns 'enc:<base64>' string."""
    if not value or value.startswith(_ENCRYPTED_PREFIX):
        return value
    return _ENCRYPTED_PREFIX + _get_fernet().encrypt(value.encode()).decode()


def decrypt_credential(value: str) -> str:
    """Decrypt an encrypted credential — returns plaintext or original if not encrypted."""
    if not value or not value.startswith(_ENCRYPTED_PREFIX):
        return value
    try:
        return _get_fernet().decrypt(value[len(_ENCRYPTED_PREFIX):].encode()).decode()
    except Exception:
        return value  # fallback — return as-is if decryption fails


def _parse_time(s) -> Optional[dt_time]:
    """Convert a time string like '09:00' or '09:00:00' to datetime.time, or pass through if already a time."""
    if s is None:
        return None
    if isinstance(s, dt_time):
        return s
    try:
        parts = str(s).split(":")
        return dt_time(int(parts[0]), int(parts[1]))
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────

class AutomationConfigUpdate(BaseModel):
    email_provider: Optional[str] = None
    sendgrid_api_key: Optional[str] = None
    sendgrid_from_email: Optional[str] = None
    sendgrid_from_name: Optional[str] = None
    gmail_address: Optional[str] = None
    gmail_app_password: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_poll_interval_seconds: Optional[int] = None
    auto_apply_threshold: Optional[float] = None
    confidence_floor: Optional[float] = None
    review_mode: Optional[str] = None
    followup_delay_days: Optional[int] = None
    max_followups: Optional[int] = None
    send_window_start: Optional[str] = None
    send_window_end: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None
    send_extraction_reply: Optional[bool] = None


class SendCollectionRequest(BaseModel):
    plan_id: str
    iso_code: str
    iso_name: str


class CustomerConfigUpdate(BaseModel):
    send_to_emails: Optional[list[str]] = None      # None = don't change; [] = clear override
    contact_name: Optional[str] = None
    preferred_language: Optional[str] = None        # 'en' | 'he'
    max_followups: Optional[int] = None
    followup_delay_days: Optional[int] = None
    send_window_start: Optional[str] = None
    send_window_end: Optional[str] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class ReviewItemBody(BaseModel):
    edited_value: Optional[str] = None  # for accept with override


class RejectBody(BaseModel):
    action: str = "rejected"            # "rejected" | "pending" | "on_hold"
    reason: Optional[str] = None        # stored as rejected_reason + task notes
    rephrased_question: Optional[str] = None  # stored in task notes when action="pending"


class ConnectionTestRequest(BaseModel):
    test_type: str                          # "smtp" | "imap" | "llm"
    email_provider: Optional[str] = None
    gmail_address: Optional[str] = None
    gmail_app_password: Optional[str] = None   # may be "••••••••" if unchanged
    sendgrid_api_key: Optional[str] = None     # may be "••••••••" if unchanged
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None


# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

@router.get("/config")
async def get_automation_config(current_user=Depends(require_operator)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.automation_config WHERE id = 1"
        )
    if not row:
        return {}
    cfg = dict(row)
    # Mask sensitive fields (decrypt first just to check they have a value, then mask)
    for field in _SENSITIVE_FIELDS:
        if cfg.get(field):
            cfg[field] = "••••••••"
    # Convert time objects to HH:MM strings for JSON serialisation
    for tf in ("send_window_start", "send_window_end"):
        if cfg.get(tf) and isinstance(cfg[tf], dt_time):
            cfg[tf] = cfg[tf].strftime("%H:%M")
    return cfg


@router.put("/config")
async def update_automation_config(
    body: AutomationConfigUpdate,
    current_user=Depends(require_operator),
):
    pool = await get_db_pool()
    updates, values, i = [], [], 1

    field_map = {
        "email_provider": body.email_provider,
        "sendgrid_from_email": body.sendgrid_from_email,
        "sendgrid_from_name": body.sendgrid_from_name,
        "gmail_address": body.gmail_address,
        "imap_host": body.imap_host,
        "imap_port": body.imap_port,
        "imap_poll_interval_seconds": body.imap_poll_interval_seconds,
        "auto_apply_threshold": body.auto_apply_threshold,
        "confidence_floor": body.confidence_floor,
        "review_mode": body.review_mode,
        "followup_delay_days": body.followup_delay_days,
        "max_followups": body.max_followups,
        "send_window_start": _parse_time(body.send_window_start),
        "send_window_end": _parse_time(body.send_window_end),
        "timezone": body.timezone,
        "enabled": body.enabled,
        "send_extraction_reply": body.send_extraction_reply,
    }
    # Sensitive fields — encrypt before saving, skip if still masked
    for field in _SENSITIVE_FIELDS:
        raw_val = getattr(body, field, None)
        if raw_val and raw_val != "••••••••":
            field_map[field] = encrypt_credential(raw_val)

    for col, val in field_map.items():
        if val is not None:
            updates.append(f"{col} = ${i}")
            values.append(val)
            i += 1

    if not updates:
        raise HTTPException(400, "Nothing to update")

    updates.append("updated_at = NOW()")
    values.append(1)  # WHERE id = 1

    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE {settings.DATABASE_APP_SCHEMA}.automation_config "
            f"SET {', '.join(updates)} WHERE id = ${i}",
            *values,
        )

    return {"ok": True}


# ──────────────────────────────────────────────────────────────
# Connection tests
# ──────────────────────────────────────────────────────────────

def _test_smtp_sync(gmail_address: str, app_password: str) -> tuple[bool, str]:
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=10) as server:
            server.login(gmail_address, app_password)
        return True, f"Connected and authenticated as {gmail_address}"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed — check Gmail address and App Password"
    except Exception as e:
        return False, str(e)


def _test_imap_sync(host: str, port: int, gmail_address: str, app_password: str) -> tuple[bool, str]:
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(gmail_address, app_password)
        status, data = mail.select("inbox")
        count = data[0].decode() if data and data[0] else "?"
        mail.logout()
        return True, f"Connected to {host}:{port} — inbox has {count} message(s)"
    except imaplib.IMAP4.error as e:
        return False, f"IMAP auth failed — {e}"
    except Exception as e:
        return False, str(e)


async def _test_sendgrid_async(api_key: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if r.status_code == 200:
            name = r.json().get("username", "")
            return True, f"SendGrid key valid — account: {name}"
        return False, f"SendGrid returned {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


async def _test_llm_async(provider: str) -> tuple[bool, str]:
    try:
        if provider == "anthropic":
            key = getattr(settings, "ANTHROPIC_API_KEY", "")
            if not key:
                return False, "ANTHROPIC_API_KEY not set in environment"
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
                          "messages": [{"role": "user", "content": "Hi"}]},
                )
            if r.status_code == 200:
                return True, "Anthropic API key valid — claude-haiku-4-5-20251001 reachable"
            return False, f"Anthropic returned {r.status_code}: {r.json().get('error',{}).get('message','')}"

        elif provider == "groq":
            key = getattr(settings, "GROQ_API_KEY", "")
            if not key:
                return False, "GROQ_API_KEY not set in environment"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 200:
                count = len(r.json().get("data", []))
                return True, f"Groq API key valid — {count} model(s) available"
            return False, f"Groq returned {r.status_code}: {r.text[:200]}"

        else:  # gemini
            key = getattr(settings, "GOOGLE_API_KEY", "")
            if not key:
                return False, "GOOGLE_API_KEY not set in environment"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                )
            if r.status_code == 200:
                count = len(r.json().get("models", []))
                return True, f"Google API key valid — {count} model(s) available"
            return False, f"Google returned {r.status_code}: {r.json().get('error',{}).get('message','')}"
    except Exception as e:
        return False, str(e)


@router.post("/test")
async def test_connection(
    body: ConnectionTestRequest,
    current_user=Depends(require_operator),
):
    """Run a live connection test for smtp / imap / llm using current (possibly unsaved) config values."""
    # Load saved config to use as fallback for masked/missing fields
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        saved = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.automation_config WHERE id = 1"
        )
    saved = dict(saved) if saved else {}

    def resolve(field: str, submitted):
        """Use submitted value unless it's masked or empty — then fall back to saved (decrypted)."""
        if submitted and submitted != "••••••••":
            return submitted
        raw = saved.get(field) or ""
        return decrypt_credential(raw) if raw else ""

    if body.test_type == "smtp":
        provider = body.email_provider or saved.get("email_provider", "gmail")
        if provider == "sendgrid":
            key = resolve("sendgrid_api_key", body.sendgrid_api_key)
            if not key:
                return {"ok": False, "message": "SendGrid API key is not configured"}
            ok, msg = await _test_sendgrid_async(key)
        else:
            gmail = resolve("gmail_address", body.gmail_address)
            pwd = resolve("gmail_app_password", body.gmail_app_password)
            if not gmail or not pwd:
                return {"ok": False, "message": "Gmail address or App Password not configured"}
            ok, msg = await asyncio.to_thread(_test_smtp_sync, gmail, pwd)
        return {"ok": ok, "message": msg}

    elif body.test_type == "imap":
        gmail = resolve("gmail_address", body.gmail_address)
        pwd = resolve("gmail_app_password", body.gmail_app_password)
        host = body.imap_host or saved.get("imap_host") or "imap.gmail.com"
        port = body.imap_port or saved.get("imap_port") or 993
        if not gmail or not pwd:
            return {"ok": False, "message": "Gmail address or App Password not configured"}
        ok, msg = await asyncio.to_thread(_test_imap_sync, host, int(port), gmail, pwd)
        return {"ok": ok, "message": msg}

    elif body.test_type == "llm":
        async with pool.acquire() as conn:
            ai_row = await conn.fetchrow(
                f"SELECT provider FROM {settings.DATABASE_APP_SCHEMA}.ai_config"
                f" WHERE service = 'extraction'"
            )
        provider = (ai_row["provider"] if ai_row else None) or "gemini"
        ok, msg = await _test_llm_async(provider)
        return {"ok": ok, "message": msg}

    raise HTTPException(400, f"Unknown test_type: {body.test_type}")


# ──────────────────────────────────────────────────────────────
# Send collection campaign
# ──────────────────────────────────────────────────────────────

@router.post("/{customer_id}/send-collection")
async def send_collection(
    customer_id: int,
    body: SendCollectionRequest,
    current_user=Depends(require_operator),
):
    """Enqueue an email collection campaign for a customer plan."""
    from ..redis_client import get_redis
    redis_wrapper = await get_redis()
    redis = redis_wrapper._client

    # Read per-customer config for overrides (contact name, language, recipient list)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        cust_cfg = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customer_automation_config WHERE customer_id = $1",
            customer_id,
        )

    msg = {
        "customer_id": str(customer_id),
        "plan_id": body.plan_id,
        "iso_code": body.iso_code,
        "iso_name": body.iso_name,
        "is_followup": "false",
        "followup_number": "1",
        "created_by": str(current_user.get("user_id") or ""),
    }
    if cust_cfg:
        if cust_cfg.get("contact_name"):
            msg["contact_name"] = cust_cfg["contact_name"]
        if cust_cfg.get("preferred_language"):
            msg["language"] = cust_cfg["preferred_language"]
        if cust_cfg.get("send_to_emails"):
            msg["send_to_override"] = json.dumps(list(cust_cfg["send_to_emails"]))

    await redis.xadd("automation:send", msg)
    return {"ok": True, "message": "Campaign queued — email will be sent shortly"}


# ──────────────────────────────────────────────────────────────
# Status per customer (thread view: campaigns with nested replies)
# ──────────────────────────────────────────────────────────────

@router.get("/{customer_id}/status")
async def get_customer_automation_status(
    customer_id: int,
    current_user=Depends(require_operator),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Campaigns ordered by sent time (join customer_iso_plans + iso_standards for iso code/name)
        campaigns = await conn.fetch(
            f"""SELECT ecr.id, ecr.plan_id, ecr.campaign_number, ecr.status,
                       ecr.sent_to, ecr.subject, ecr.sent_at, ecr.expires_at,
                       ecr.questions_snapshot, ecr.evidence_snapshot,
                       iso.code AS iso_code, iso.name AS iso_name
                FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests ecr
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans cip ON cip.id = ecr.plan_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = cip.iso_standard_id
                WHERE ecr.customer_id = $1
                ORDER BY ecr.sent_at DESC NULLS LAST
                LIMIT 20""",
            customer_id,
        )

        # Inbound replies with extraction counts + LLM notes + body snippet
        inbound = await conn.fetch(
            f"""SELECT il.id, il.collection_request_id, il.from_email, il.subject,
                       il.status, il.received_at, il.extraction_result,
                       LEFT(il.body_text, 300) AS body_snippet,
                       COUNT(ei.id) FILTER (WHERE ei.status IN ('auto_applied','accepted')) AS auto_applied,
                       COUNT(ei.id) FILTER (WHERE ei.status = 'pending') AS pending_review,
                       COUNT(ei.id) AS total_extracted
                FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log il
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.email_extraction_items ei
                       ON ei.inbound_log_id = il.id
                WHERE il.customer_id = $1
                  AND il.status IN ('applied','extracted','processing','received')
                GROUP BY il.id
                ORDER BY il.received_at""",
            customer_id,
        )

        # Pending review items (include task title for context)
        review_items = await conn.fetch(
            f"""SELECT ei.id, ei.item_type, ei.placeholder_key, ei.task_id,
                       ei.extracted_value, ei.confidence, ei.reasoning,
                       ei.status, ei.created_at, ei.plan_id,
                       COALESCE(
                           (SELECT ct.title FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                            WHERE ct.customer_id = ei.customer_id
                              AND ct.placeholder_key = ei.placeholder_key
                              AND ct.status != 'cancelled'
                            ORDER BY ct.created_at DESC LIMIT 1),
                           (SELECT ct.title FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                            WHERE ct.id = ei.task_id LIMIT 1)
                       ) AS task_title
                FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items ei
                WHERE ei.customer_id = $1 AND ei.status = 'pending'
                ORDER BY ei.confidence DESC""",
            customer_id,
        )

        # Global counts (all history, not just the 20 recent)
        total_campaigns = await conn.fetchval(
            f"SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests WHERE customer_id = $1",
            customer_id,
        )
        total_replies = await conn.fetchval(
            f"""SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log
                WHERE customer_id = $1 AND status IN ('applied','extracted')""",
            customer_id,
        )
        auto_applied_total = await conn.fetchval(
            f"""SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                WHERE customer_id = $1 AND status IN ('auto_applied','accepted')""",
            customer_id,
        )

        # Sent placeholder keys for task badge
        sent_key_rows = await conn.fetch(
            f"""SELECT DISTINCT elem->>'placeholder_key' AS k
                FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests,
                     jsonb_array_elements(questions_snapshot) AS elem
                WHERE customer_id = $1 AND status != 'expired'
                  AND elem->>'placeholder_key' IS NOT NULL""",
            customer_id,
        )

    def _serialize(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                out[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                out[k] = str(v)
            elif isinstance(v, list):
                out[k] = [str(i) if isinstance(i, uuid.UUID) else i for i in v]
            else:
                out[k] = v
        return out

    def _parse_jsonb(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return val if val is not None else []

    # Group inbound replies by campaign id; orphan replies have no collection_request_id
    from collections import defaultdict
    replies_by_campaign: dict = defaultdict(list)
    orphan_replies = []
    for r in inbound:
        rd = _serialize(dict(r))
        # Extract LLM notes from extraction_result JSONB
        er = _parse_jsonb(r["extraction_result"])
        rd["extraction_notes"] = er.get("notes") if isinstance(er, dict) else None
        del rd["extraction_result"]  # don't send full LLM result
        cid = str(r["collection_request_id"]) if r["collection_request_id"] else None
        if cid:
            replies_by_campaign[cid].append(rd)
        else:
            orphan_replies.append(rd)  # replied without token — matched by sender email

    # Build threads
    threads = []
    for c in campaigns:
        cd = _serialize(dict(c))
        cd["questions_snapshot"] = _parse_jsonb(c["questions_snapshot"])
        cd["evidence_snapshot"] = _parse_jsonb(c["evidence_snapshot"])
        cd["replies"] = replies_by_campaign.get(cd["id"], [])
        threads.append(cd)

    return {
        "threads": threads,
        "orphan_replies": orphan_replies,
        "review_queue": [_serialize(dict(r)) for r in review_items],
        "summary": {
            "total_campaigns": total_campaigns,
            "total_replies": total_replies,
            "auto_applied": auto_applied_total,
            "pending_review": len(review_items),
        },
        "sent_placeholder_keys": [r["k"] for r in sent_key_rows if r["k"]],
    }


@router.get("/{customer_id}/sent-keys")
async def get_sent_placeholder_keys(
    customer_id: int,
    current_user=Depends(require_operator),
):
    """Lightweight endpoint: returns placeholder_keys sent via automation campaigns."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT DISTINCT elem->>'placeholder_key' AS k
                FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests,
                     jsonb_array_elements(questions_snapshot) AS elem
                WHERE customer_id = $1 AND status != 'expired'
                  AND elem->>'placeholder_key' IS NOT NULL""",
            customer_id,
        )
    return {"sent_placeholder_keys": [r["k"] for r in rows if r["k"]]}


# ──────────────────────────────────────────────────────────────
# Review queue (global)
# ──────────────────────────────────────────────────────────────

@router.get("/review-queue")
async def get_global_review_queue(
    limit: int = 50,
    current_user=Depends(require_operator),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT ei.id, ei.item_type, ei.placeholder_key, ei.task_id,
                       ei.extracted_value, ei.confidence, ei.reasoning,
                       ei.status, ei.created_at, ei.plan_id,
                       c.name AS customer_name, c.id AS customer_id_out,
                       iso.code AS iso_code,
                       COALESCE(
                           (SELECT ct.title FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                            WHERE ct.customer_id = ei.customer_id
                              AND ct.placeholder_key = ei.placeholder_key
                              AND ct.status != 'cancelled'
                            ORDER BY ct.created_at DESC LIMIT 1),
                           (SELECT ct.title FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
                            WHERE ct.id = ei.task_id LIMIT 1)
                       ) AS task_title
                FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items ei
                JOIN {settings.DATABASE_APP_SCHEMA}.customers c ON c.id = ei.customer_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans cip ON cip.id = ei.plan_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON iso.id = cip.iso_standard_id
                WHERE ei.status = 'pending'
                ORDER BY ei.confidence DESC, ei.created_at
                LIMIT $1""",
            limit,
        )

    def _row(r):
        d = dict(r)
        # customer_id_out is an alias we used to avoid collision with ei.customer_id
        if "customer_id_out" in d:
            d["customer_id"] = d.pop("customer_id_out")
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                d[k] = str(v)
        return d

    return [_row(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# Accept / Reject review item
# ──────────────────────────────────────────────────────────────

@router.post("/review-item/{item_id}/accept")
async def accept_review_item(
    item_id: str,
    body: ReviewItemBody,
    current_user=Depends(require_operator),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        item = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items WHERE id = $1",
            item_id,
        )
        if not item:
            raise HTTPException(404, "Item not found")
        if item["status"] not in ("pending",):
            raise HTTPException(400, f"Item already {item['status']}")

        final_value = body.edited_value or item["extracted_value"]
        user_id = current_user.get("user_id")

        if item["item_type"] == "answer" and item["placeholder_key"]:
            # 1. Upsert profile data (verified = true since human reviewed it)
            await conn.execute(
                f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_profile_data
                    (customer_id, field_key, field_value, source, verified, confidence,
                     filled_via, filled_at)
                    VALUES ($1,$2,$3,'email',true,95,'review_accepted',NOW())
                    ON CONFLICT (customer_id, field_key) DO UPDATE SET
                        field_value = EXCLUDED.field_value, source='email',
                        verified=true, filled_via='review_accepted',
                        filled_at=NOW(), updated_at=NOW()""",
                item["customer_id"], item["placeholder_key"], final_value,
            )
            # 2. Update task to 'answered' (trigger fires from step 3 to push it to 'completed')
            await conn.execute(
                f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                    SET answer = $3, answered_at = COALESCE(answered_at, NOW()),
                        answered_via = COALESCE(answered_via, 'email'), updated_at = NOW(),
                        extraction_confidence = $4,
                        extraction_reasoning  = $5,
                        reviewed_by_human     = TRUE,
                        status = CASE WHEN status = 'pending' THEN 'answered' ELSE status END
                    WHERE customer_id = $1 AND placeholder_key = $2
                      AND status NOT IN ('completed', 'cancelled')""",
                item["customer_id"], item["placeholder_key"], final_value,
                float(item["confidence"] or 0), item["reasoning"],
            )
            # 3. Update placeholder → fires trg_placeholder_to_task → task.status = 'completed'
            await conn.execute(
                f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                    SET status = 'collected', updated_at = NOW()
                    WHERE customer_id = $1 AND placeholder_key = $2
                      AND ($3::uuid IS NULL OR plan_id = $3)""",
                item["customer_id"], item["placeholder_key"], item["plan_id"],
            )

        elif item["item_type"] == "evidence" and item["task_id"]:
            filename = item["extracted_value"] or ""
            # Look up storage_path from the inbound log's attachments JSONB
            log_row = await conn.fetchrow(
                f"SELECT attachments FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log WHERE id = $1",
                item["inbound_log_id"],
            )
            storage_path = ""
            if log_row and log_row["attachments"]:
                raw_atts = log_row["attachments"]
                atts = json.loads(raw_atts) if isinstance(raw_atts, str) else (raw_atts or [])
                att = next((a for a in atts if isinstance(a, dict) and a.get("filename") == filename), {})
                storage_path = att.get("storage_path", "")
                # storage_path was recorded by automation-service where the volume mounts as
                # /app/storage/customers/ → host ./dashboard/backend/storage/.
                # In this backend container the same host dir is /app/storage/, so strip
                # the extra "customers/" segment to get the correct local path.
                if storage_path.startswith("/app/storage/customers/"):
                    storage_path = "/app/storage/" + storage_path[len("/app/storage/customers/"):]

            # Copy file to customer evidence dir (best-effort)
            # Backend volume: ./dashboard/backend → /app, so evidence lands at /app/storage/{id}/evidence/...
            task_id_str = str(item["task_id"])
            dest_dir = Path(f"/app/storage/{item['customer_id']}/evidence/{task_id_str}")
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / filename
            if storage_path and Path(storage_path).exists():
                shutil.copy2(storage_path, dest)

            confidence_val = float(item["confidence"] or 0)
            reasoning_val = item["reasoning"] or None
            file_entry = json.dumps([{
                "filename": filename,
                "path": str(dest),
                "source": "email",
                "confidence": confidence_val,
                "reasoning": reasoning_val,
                "uploaded_at": datetime.utcnow().isoformat(),
            }])
            await conn.execute(
                f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                    SET evidence_uploaded = TRUE,
                        evidence_files = COALESCE(evidence_files, '[]'::jsonb) || $2::jsonb,
                        status = 'completed',
                        answered_via = COALESCE(answered_via, 'email'),
                        answered_at  = COALESCE(answered_at, NOW()),
                        extraction_confidence = $3,
                        extraction_reasoning  = $4,
                        reviewed_by_human     = TRUE,
                        updated_at   = NOW()
                    WHERE id = $1::uuid AND status != 'cancelled'""",
                task_id_str, file_entry, confidence_val, reasoning_val,
            )

        # Mark accepted
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                SET status = 'accepted', extracted_value = $2,
                    reviewed_by = $3, reviewed_at = NOW(), applied_at = NOW()
                WHERE id = $1""",
            item_id, final_value, user_id,
        )

    return {"ok": True}


@router.post("/review-item/{item_id}/reject")
async def reject_review_item(
    item_id: str,
    body: RejectBody,
    current_user=Depends(require_operator),
):
    """
    Reject an extraction item with an action for the underlying task:
    - action="rejected": mark item rejected; task unchanged
    - action="pending":  mark item rejected; reset task to pending; optionally store rephrased question in task notes
    - action="on_hold":  mark item rejected; set task to on_hold; optionally store reason in task notes
    """
    pool = await get_db_pool()
    user_id = current_user.get("user_id")
    async with pool.acquire() as conn:
        item = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items WHERE id = $1",
            item_id,
        )
        if not item:
            raise HTTPException(404, "Item not found")
        if item["status"] not in ("pending",):
            raise HTTPException(400, f"Item already {item['status']}")

        # Handle task action for answer-type items
        if item["item_type"] == "answer" and item["placeholder_key"]:
            if body.action == "pending":
                # Build notes from reason + rephrased question
                notes_parts = []
                if body.reason:
                    notes_parts.append(f"Rejected: {body.reason}")
                if body.rephrased_question:
                    notes_parts.append(f"Rephrased question: {body.rephrased_question}")
                notes = "\n".join(notes_parts) if notes_parts else None
                set_clauses = (
                    "status = 'pending', answer = NULL, answered_at = NULL, "
                    "answered_via = NULL, updated_at = NOW(), "
                    "notes = CASE WHEN $3::text IS NOT NULL THEN $3 ELSE notes END"
                )
                params: list = [item["customer_id"], item["placeholder_key"], notes]
                if body.rephrased_question:
                    set_clauses += ", title = $4"
                    params.append(body.rephrased_question)
                await conn.execute(
                    f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                        SET {set_clauses}
                        WHERE customer_id = $1 AND placeholder_key = $2
                          AND status NOT IN ('completed', 'cancelled')""",
                    *params,
                )
            elif body.action == "on_hold":
                notes = body.reason or "Extraction rejected — held for manual review"
                await conn.execute(
                    f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                        SET status = 'on_hold', updated_at = NOW(),
                            notes = COALESCE($3, notes)
                        WHERE customer_id = $1 AND placeholder_key = $2
                          AND status NOT IN ('completed', 'cancelled')""",
                    item["customer_id"], item["placeholder_key"], notes,
                )
            # action="rejected" — no task change

        # Mark extraction item as rejected
        result = await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                SET status = 'rejected', rejected_reason = $2,
                    reviewed_by = $3, reviewed_at = NOW()
                WHERE id = $1 AND status = 'pending'""",
            item_id, body.reason, user_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Item not found or already reviewed")
    return {"ok": True}


# ──────────────────────────────────────────────────────────────
# Inbound webhook (SendGrid / future)
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# Thread management (delete / cancel)
# ──────────────────────────────────────────────────────────────

@router.delete("/threads/{campaign_id}")
async def delete_thread(
    campaign_id: str,
    current_user=Depends(require_operator),
):
    """
    Hard-delete a campaign thread and its linked inbound log rows.
    Applied customer profile data is preserved — only the automation records are removed.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Verify it exists and belongs to some customer (no customer scoping needed — operators only)
        row = await conn.fetchrow(
            f"SELECT id, customer_id FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests WHERE id = $1",
            campaign_id,
        )
        if not row:
            raise HTTPException(404, "Thread not found")

        # Delete extraction items for all inbound logs linked to this campaign
        await conn.execute(
            f"""DELETE FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items
                WHERE inbound_log_id IN (
                    SELECT id FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log
                    WHERE collection_request_id = $1
                )""",
            campaign_id,
        )
        # Delete linked inbound log rows
        await conn.execute(
            f"""DELETE FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log
                WHERE collection_request_id = $1""",
            campaign_id,
        )
        # Delete the campaign itself
        await conn.execute(
            f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.email_collection_requests WHERE id = $1",
            campaign_id,
        )
    return {"ok": True}


@router.post("/threads/{campaign_id}/cancel")
async def cancel_thread(
    campaign_id: str,
    current_user=Depends(require_operator),
):
    """
    Cancel a pending campaign thread — stops follow-up emails from being sent.
    All data (inbound logs, extracted items, profile data) is preserved.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.email_collection_requests
                SET status = 'cancelled'
                WHERE id = $1 AND status = 'pending'""",
            campaign_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Thread not found or not in pending state")
    return {"ok": True}


# ──────────────────────────────────────────────────────────────
# Per-customer automation config
# ──────────────────────────────────────────────────────────────

@router.get("/{customer_id}/config")
async def get_customer_automation_config(
    customer_id: int,
    current_user=Depends(require_operator),
):
    """Get per-customer automation config (overrides global defaults)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT * FROM {settings.DATABASE_APP_SCHEMA}.customer_automation_config WHERE customer_id = $1",
            customer_id,
        )
    if not row:
        return {"customer_id": customer_id, "enabled": True, "preferred_language": "en"}
    cfg = dict(row)
    for tf in ("send_window_start", "send_window_end"):
        if cfg.get(tf) and isinstance(cfg[tf], dt_time):
            cfg[tf] = cfg[tf].strftime("%H:%M")
    return cfg


@router.put("/{customer_id}/config")
async def update_customer_automation_config(
    customer_id: int,
    body: CustomerConfigUpdate,
    current_user=Depends(require_operator),
):
    """Upsert per-customer automation config."""
    pool = await get_db_pool()

    fields = {
        "contact_name": body.contact_name,
        "preferred_language": body.preferred_language,
        "max_followups": body.max_followups,
        "followup_delay_days": body.followup_delay_days,
        "send_window_start": _parse_time(body.send_window_start),
        "send_window_end": _parse_time(body.send_window_end),
        "enabled": body.enabled,
        "notes": body.notes,
    }
    # send_to_emails uses special handling (can be cleared to NULL with empty list)
    send_to_emails = body.send_to_emails  # None = skip; [] = clear; [...] = set

    non_null = {k: v for k, v in fields.items() if v is not None}

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            f"SELECT customer_id FROM {settings.DATABASE_APP_SCHEMA}.customer_automation_config WHERE customer_id = $1",
            customer_id,
        )
        if not existing:
            # INSERT with defaults
            await conn.execute(
                f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_automation_config
                    (customer_id, send_to_emails, contact_name, preferred_language,
                     max_followups, followup_delay_days, send_window_start, send_window_end,
                     enabled, notes)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                customer_id,
                send_to_emails if send_to_emails is not None else None,
                fields.get("contact_name"),
                fields.get("preferred_language") or "en",
                fields.get("max_followups"),
                fields.get("followup_delay_days"),
                fields.get("send_window_start"),
                fields.get("send_window_end"),
                fields.get("enabled") if fields.get("enabled") is not None else True,
                fields.get("notes"),
            )
        else:
            # UPDATE — only update provided fields
            updates, values, i = ["updated_at = NOW()"], [], 1
            if send_to_emails is not None:
                updates.append(f"send_to_emails = ${i}"); values.append(send_to_emails or None); i += 1
            for col, val in non_null.items():
                updates.append(f"{col} = ${i}"); values.append(val); i += 1
            if len(values) == 0:
                return {"ok": True}
            values.append(customer_id)
            await conn.execute(
                f"UPDATE {settings.DATABASE_APP_SCHEMA}.customer_automation_config "
                f"SET {', '.join(updates)} WHERE customer_id = ${i}",
                *values,
            )
    return {"ok": True}


@router.get("/inbound-emails")
async def get_inbound_emails(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(require_operator),
):
    """Paginated list of all inbound emails with extraction summary."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT
                l.id, l.customer_id, l.from_email, l.subject,
                l.status, l.received_at, l.processed_at,
                c.name AS customer_name,
                COALESCE(
                    (SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items e
                     WHERE e.inbound_log_id = l.id), 0
                ) AS total_items,
                COALESCE(
                    (SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items e
                     WHERE e.inbound_log_id = l.id AND e.status = 'auto_applied'), 0
                ) AS auto_applied,
                COALESCE(
                    (SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items e
                     WHERE e.inbound_log_id = l.id AND e.status = 'pending'), 0
                ) AS pending_review,
                COALESCE(
                    (SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.email_extraction_items e
                     WHERE e.inbound_log_id = l.id AND e.status = 'accepted'), 0
                ) AS accepted,
                l.extraction_result->>'notes' AS llm_notes,
                COALESCE(jsonb_array_length(l.attachments), 0) AS attachment_count,
                l.attachments
            FROM {settings.DATABASE_APP_SCHEMA}.email_inbound_log l
            LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customers c ON c.id = l.customer_id
            ORDER BY l.received_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)
    result = []
    for r in rows:
        d = dict(r)
        raw_atts = d.pop("attachments", None)
        atts = json.loads(raw_atts) if isinstance(raw_atts, str) else (raw_atts or [])
        d["attachment_filenames"] = [a.get("filename", "") for a in atts if isinstance(a, dict)]
        result.append(d)
    return result


@router.post("/trigger-imap-poll")
async def trigger_imap_poll(current_user=Depends(require_operator)):
    """Manually trigger one IMAP poll cycle — useful for testing or immediate check."""
    from ..redis_client import get_redis
    redis_wrapper = await get_redis()
    redis = redis_wrapper._client
    # Push a special control message to automation:send so the service re-polls immediately
    await redis.xadd("automation:imap_trigger", {"trigger": "manual", "by": str(current_user.get("user_id", ""))})
    return {"ok": True, "message": "IMAP poll triggered — inbox will be checked within seconds"}


@router.post("/webhooks/email-inbound")
async def email_inbound_webhook(request_data: dict):
    """
    Receives parsed email from SendGrid Inbound Parse webhook.
    No auth — verified by X-Twilio-Email-Event-Webhook-Signature header (TODO).
    """
    from ..redis_client import get_redis
    import re

    to_field = request_data.get("to", "") or request_data.get("envelope", {}).get("to", "")
    from_email = request_data.get("from", "")
    subject = request_data.get("subject", "")
    body_text = request_data.get("text", "")

    # Extract token from to address
    token_match = re.search(r'collect_([a-zA-Z0-9]{16,64})', to_field)
    token = token_match.group(1) if token_match else None

    redis_wrapper = await get_redis()
    redis = redis_wrapper._client
    await redis.xadd("automation:extract", {
        "token": token or "",
        "from_email": from_email,
        "subject": subject,
        "body_text": body_text[:10000],
        "attachments": json.dumps([]),
    })
    return {"ok": True}
