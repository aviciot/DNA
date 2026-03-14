import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.db import get_pool, validate_token, log_activity
from app.upload import process_upload

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Token exchange → httpOnly cookie ─────────────────────────────────────────

@router.get("/auth")
async def exchange_token(token: str, request: Request):
    """Validate token from email link, set httpOnly cookie, redirect to portal."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT id, customer_id FROM {settings.database_app_schema}.customer_portal_access
                WHERE token = $1 AND expires_at > NOW()""",
            token,
        )
    if not row:
        return RedirectResponse(url="/expired")

    # Update last seen timestamp
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE {settings.database_app_schema}.customer_portal_access SET last_used_at = NOW() WHERE token = $1",
            token,
        )

    await log_activity("token_validated", token, row["customer_id"],
                       ip=request.client.host if request.client else None)

    response = RedirectResponse(url="/")
    response.set_cookie(
        key="portal_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.portal_token_max_age_days * 86400,
        path="/",
    )
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("portal_token", path="/")
    return response


# ── Portal data endpoints (all require valid cookie) ─────────────────────────

@router.get("/me")
async def get_me(session: dict = Depends(validate_token)):
    return {
        "customer_name": session["customer_name"],
        "contact_person": session["contact_person"],
        "contact_email": session["contact_email"],
        "iso_code": session["iso_code"],
        "iso_name": session["iso_name"],
        "plan_name": session["plan_name"],
        "target_completion_date": str(session["target_completion_date"]) if session["target_completion_date"] else None,
    }


@router.get("/progress")
async def get_progress(request: Request, session: dict = Depends(validate_token)):
    plan_id = request.query_params.get("plan_id") or session["plan_id"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT
                    COUNT(*) FILTER (WHERE is_ignored = false) AS total,
                    COUNT(*) FILTER (WHERE status IN ('completed','answered') AND is_ignored = false) AS completed,
                    COUNT(*) FILTER (WHERE status = 'pending' AND is_ignored = false) AS pending,
                    COUNT(*) FILTER (WHERE requires_evidence = true AND evidence_uploaded = false AND is_ignored = false) AS evidence_pending
                FROM {settings.database_app_schema}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2::uuid""",
            session["customer_id"], plan_id,
        )
    total = row["total"] or 0
    completed = row["completed"] or 0
    return {
        "total": total,
        "completed": completed,
        "pending": row["pending"] or 0,
        "evidence_pending": row["evidence_pending"] or 0,
        "percentage": round((completed / total * 100)) if total else 0,
        "target_completion_date": str(session["target_completion_date"]) if session["target_completion_date"] else None,
    }


@router.get("/questions")
async def get_questions(request: Request, session: dict = Depends(validate_token)):
    plan_id = request.query_params.get("plan_id") or session["plan_id"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT id, title, description, task_type, status, priority,
                       placeholder_key, answer, requires_evidence, evidence_uploaded,
                       evidence_description, due_date
                FROM {settings.database_app_schema}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2::uuid
                  AND is_ignored = false
                  AND status NOT IN ('cancelled')
                ORDER BY
                    CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                    created_at""",
            session["customer_id"], plan_id,
        )
    return [dict(r) for r in rows]


class AnswerPayload(BaseModel):
    task_id: str
    placeholder_key: str
    value: str


@router.post("/answer")
async def submit_answer(payload: AnswerPayload, request: Request,
                        session: dict = Depends(validate_token)):
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify task belongs to this customer
        task = await conn.fetchrow(
            f"""SELECT id FROM {settings.database_app_schema}.customer_tasks
                WHERE id = $1::uuid AND customer_id = $2
                  AND status != 'cancelled'""",
            payload.task_id, session["customer_id"],
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        await conn.execute(
            f"""UPDATE {settings.database_app_schema}.customer_tasks
                SET answer = $2,
                    answered_via = 'customer_portal',
                    answered_at = NOW(),
                    answered_by_name = $3,
                    status = 'completed',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1::uuid""",
            payload.task_id, payload.value, session["customer_name"],
        )
        # Upsert profile data
        await conn.execute(
            f"""INSERT INTO {settings.database_app_schema}.customer_profile_data
                (customer_id, field_key, field_value, source, filled_via, filled_at)
                VALUES ($1, $2, $3, 'portal', 'portal', NOW())
                ON CONFLICT (customer_id, field_key) DO UPDATE
                SET field_value = EXCLUDED.field_value, filled_via = 'portal',
                    filled_at = NOW(), updated_at = NOW()""",
            session["customer_id"], payload.placeholder_key, payload.value,
        )

        # Check if this is a KYC task — if all batch answers done, queue adjustment
        kyc = await conn.fetchrow(
            f"""SELECT ct.kyc_batch_id, ct.plan_id
                FROM {settings.database_app_schema}.customer_tasks ct
                WHERE ct.id = $1::uuid AND ct.task_type = 'kyc_question'
                  AND ct.kyc_batch_id IS NOT NULL""",
            payload.task_id,
        )
        if kyc and kyc["kyc_batch_id"]:
            answered = await conn.fetchval(
                f"""SELECT COUNT(*) FROM {settings.database_app_schema}.customer_tasks
                    WHERE kyc_batch_id = $1::uuid AND task_type = 'kyc_question'
                      AND status IN ('answered', 'completed', 'answered')
                      AND (is_ignored = FALSE OR is_ignored IS NULL)""",
                kyc["kyc_batch_id"],
            )
            total = await conn.fetchval(
                f"""SELECT total_questions FROM {settings.database_app_schema}.iso360_kyc_batches
                    WHERE id = $1::uuid""",
                kyc["kyc_batch_id"],
            )
            if total and answered >= total:
                # All answered — queue adjustment pass
                import uuid as _uuid2
                plan_row = await conn.fetchrow(
                    f"""SELECT p.iso_standard_id, iso.code,
                               COALESCE(ps.reminder_month::text, '') AS reminder_month,
                               COALESCE(ps.reminder_day::text, '')   AS reminder_day,
                               COALESCE(p.preferred_language, c.preferred_language, 'en') AS language
                        FROM {settings.database_app_schema}.customer_iso_plans p
                        JOIN {settings.database_app_schema}.iso_standards iso ON iso.id = p.iso_standard_id
                        JOIN {settings.database_app_schema}.customers c ON c.id = p.customer_id
                        LEFT JOIN {settings.database_app_schema}.iso360_plan_settings ps ON ps.plan_id = p.id
                        WHERE p.id = $1""",
                    kyc["plan_id"],
                )
                if plan_row:
                    import redis.asyncio as _aioredis
                    _r = _aioredis.from_url(settings.redis_url, decode_responses=True)
                    job_id = str(_uuid2.uuid4())
                    await _r.xadd("ai:iso360_adjustment", {
                        "job_id":          job_id,
                        "plan_id":         str(kyc["plan_id"]),
                        "customer_id":     str(session["customer_id"]),
                        "iso_standard_id": str(plan_row["iso_standard_id"]),
                        "iso_standard":    plan_row["code"],
                        "reminder_month":  plan_row["reminder_month"],
                        "reminder_day":    plan_row["reminder_day"],
                        "kyc_batch_id":    str(kyc["kyc_batch_id"]),
                        "language":        plan_row["language"],
                    })
                    # Mark batch as triggered
                    await conn.execute(
                        f"""UPDATE {settings.database_app_schema}.iso360_kyc_batches
                            SET status = 'adjustment_triggered' WHERE id = $1::uuid""",
                        kyc["kyc_batch_id"],
                    )

    await log_activity("answer_submitted", session["token"], session["customer_id"],
                       detail={"task_id": payload.task_id, "key": payload.placeholder_key},
                       ip=request.client.host if request.client else None)
    return {"ok": True}


@router.post("/upload/{task_id}")
async def upload_evidence(task_id: str, request: Request,
                          file: UploadFile = File(...),
                          session: dict = Depends(validate_token)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        task = await conn.fetchrow(
            f"""SELECT id FROM {settings.database_app_schema}.customer_tasks
                WHERE id = $1::uuid AND customer_id = $2
                  AND ($3::uuid IS NULL OR plan_id = $3::uuid)
                  AND status != 'cancelled'""",
            task_id, session["customer_id"],
            str(session["plan_id"]) if session["plan_id"] else None,
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

    meta = await process_upload(file, session["customer_id"], task_id)

    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.database_app_schema}.customer_tasks
                SET evidence_uploaded = true,
                    evidence_files = COALESCE(evidence_files, '[]'::jsonb) || $2::jsonb,
                    status = 'completed',
                    completed_at = NOW(),
                    answered_via = 'customer_portal',
                    answered_at = NOW(),
                    answered_by_name = $3,
                    updated_at = NOW()
                WHERE id = $1::uuid""",
            task_id,
            json.dumps([{
                "filename": meta["original_filename"],
                "path": meta["storage_path"],
                "source": "portal",
                "uploaded_at": __import__("datetime").datetime.utcnow().isoformat(),
            }]),
            session["customer_name"],
        )

    await log_activity("file_uploaded", session["token"], session["customer_id"],
                       detail={"task_id": task_id, "filename": meta["original_filename"],
                               "size": meta["size_bytes"]},
                       ip=request.client.host if request.client else None)
    return {"ok": True, "filename": meta["original_filename"]}


@router.get("/plans")
async def get_plans(session: dict = Depends(validate_token)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT cip.id, cip.plan_name, iso.code AS iso_code, iso.name AS iso_name,
                       cip.target_completion_date,
                       COUNT(ct.id) FILTER (WHERE ct.is_ignored = false) AS total,
                       COUNT(ct.id) FILTER (WHERE ct.status IN ('completed','answered') AND ct.is_ignored = false) AS completed
                FROM {settings.database_app_schema}.customer_iso_plans cip
                JOIN {settings.database_app_schema}.iso_standards iso ON iso.id = cip.iso_standard_id
                LEFT JOIN {settings.database_app_schema}.customer_tasks ct ON ct.plan_id = cip.id
                WHERE cip.customer_id = $1
                GROUP BY cip.id, iso.code, iso.name
                ORDER BY cip.created_at""",
            session["customer_id"],
        )
    return [dict(r) for r in rows]


@router.get("/history")
async def get_history(session: dict = Depends(validate_token)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT event, detail, ip_address, created_at
                FROM {settings.database_app_schema}.portal_activity_log
                WHERE customer_id = $1 AND token = $2
                ORDER BY created_at DESC LIMIT 100""",
            session["customer_id"], session["token"],
        )
    return [dict(r) for r in rows]


@router.get("/iso360")
async def get_iso360_data(request: Request, session: dict = Depends(validate_token)):
    """Return ISO360 status, personalised activities, and KYC profile for the active plan."""
    import json as _json
    from datetime import date as _date

    plan_id = request.query_params.get("plan_id") or session["plan_id"]
    customer_id = session["customer_id"]
    pool = await get_pool()

    async with pool.acquire() as conn:
        plan_row = await conn.fetchrow(
            f"""SELECT p.iso360_enabled, s.adjustment_pass_done
                FROM {settings.database_app_schema}.customer_iso_plans p
                LEFT JOIN {settings.database_app_schema}.iso360_plan_settings s ON s.plan_id = p.id
                WHERE p.id = $1::uuid AND p.customer_id = $2""",
            plan_id, customer_id,
        )

        if not plan_row or not plan_row["iso360_enabled"]:
            return {"enabled": False, "adjustment_pass_done": False,
                    "activities": [], "profile": [], "stats": {}}

        activity_rows = await conn.fetch(
            f"""SELECT cd.id, cd.document_name, cd.next_due_date, cd.last_completed_at,
                       cd.status, cd.content,
                       t.placeholder_key, t.type, t.update_frequency
                FROM {settings.database_app_schema}.customer_documents cd
                JOIN {settings.database_app_schema}.iso360_templates t ON cd.iso360_template_id = t.id
                WHERE cd.customer_id = $1 AND cd.plan_id = $2::uuid
                  AND cd.excluded = false
                ORDER BY cd.next_due_date ASC NULLS LAST, t.update_frequency""",
            customer_id, plan_id,
        )

        profile_rows = await conn.fetch(
            f"""SELECT field_key, field_value, display_label
                FROM {settings.database_app_schema}.customer_profile_data
                WHERE customer_id = $1
                ORDER BY created_at""",
            customer_id,
        )

    today = _date.today()
    activities = []
    for r in activity_rows:
        content = _json.loads(r["content"]) if isinstance(r["content"], str) else (r["content"] or {})
        due = r["next_due_date"]
        completed_at = r["last_completed_at"]

        if completed_at:
            urgency = "completed"
        elif due is None:
            urgency = "upcoming"
        elif due < today:
            urgency = "overdue"
        elif (due - today).days <= 30:
            urgency = "due_soon"
        else:
            urgency = "upcoming"

        activities.append({
            "id": str(r["id"]),
            "placeholder_key": r["placeholder_key"],
            "title": content.get("title") or r["document_name"],
            "type": r["type"],
            "update_frequency": r["update_frequency"],
            "next_due_date": str(due) if due else None,
            "last_completed_at": completed_at.isoformat() if completed_at else None,
            "urgency": urgency,
            "steps": content.get("steps", []),
            "evidence_fields": content.get("evidence_fields", []),
            "responsible_role": content.get("responsible_role"),
        })

    total = len(activities)
    done = sum(1 for a in activities if a["urgency"] == "completed")
    overdue = sum(1 for a in activities if a["urgency"] == "overdue")
    due_soon = sum(1 for a in activities if a["urgency"] == "due_soon")

    return {
        "enabled": True,
        "adjustment_pass_done": bool(plan_row["adjustment_pass_done"]),
        "activities": activities,
        "profile": [{"key": r["field_key"], "value": r["field_value"], "label": r["display_label"]} for r in profile_rows],
        "stats": {
            "total": total, "done": done, "overdue": overdue,
            "due_soon": due_soon,
            "score": round(done / total * 100) if total else 0,
        },
    }


class CompleteActivityPayload(BaseModel):
    document_id: str

@router.post("/iso360/complete")
async def mark_iso360_complete(payload: CompleteActivityPayload, request: Request, session: dict = Depends(validate_token)):
    """Mark an ISO360 activity as complete; advance next_due_date by frequency interval."""
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            f"""SELECT cd.id, t.update_frequency
                FROM {settings.database_app_schema}.customer_documents cd
                JOIN {settings.database_app_schema}.iso360_templates t ON t.id = cd.iso360_template_id
                WHERE cd.id = $1::uuid AND cd.customer_id = $2 AND cd.excluded = false""",
            payload.document_id, session["customer_id"],
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Activity not found")

        freq = doc["update_frequency"]
        interval_map = {"monthly": "1 month", "quarterly": "3 months", "yearly": "1 year"}
        interval = interval_map.get(freq)

        if interval:
            await conn.execute(
                f"""UPDATE {settings.database_app_schema}.customer_documents
                    SET last_completed_at = NOW(),
                        next_due_date = COALESCE(next_due_date, CURRENT_DATE) + $2::interval,
                        status = 'completed', updated_at = NOW()
                    WHERE id = $1::uuid""",
                payload.document_id, interval,
            )
        else:
            await conn.execute(
                f"""UPDATE {settings.database_app_schema}.customer_documents
                    SET last_completed_at = NOW(), status = 'completed', updated_at = NOW()
                    WHERE id = $1::uuid""",
                payload.document_id,
            )

        # Mark any open customer_tasks for this document as completed
        await conn.execute(
            f"""UPDATE {settings.database_app_schema}.customer_tasks
                SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                WHERE document_id = $1::uuid AND customer_id = $2
                  AND status NOT IN ('completed', 'cancelled')""",
            payload.document_id, session["customer_id"],
        )

    await log_activity("iso360_activity_completed", session["token"], session["customer_id"],
                       detail={"document_id": payload.document_id},
                       ip=request.client.host if request.client else None)
    return {"ok": True}


@router.post("/iso360/upload/{document_id}")
async def upload_iso360_evidence(document_id: str, request: Request,
                                  file: UploadFile = File(...),
                                  session: dict = Depends(validate_token)):
    """Upload evidence for an ISO360 activity. Finds or creates a customer_task then delegates to the secure upload pipeline."""
    import json as _json, uuid as _uuid
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify document belongs to customer
        doc = await conn.fetchrow(
            f"""SELECT cd.id, cd.plan_id, cd.document_name, t.placeholder_key
                FROM {settings.database_app_schema}.customer_documents cd
                JOIN {settings.database_app_schema}.iso360_templates t ON t.id = cd.iso360_template_id
                WHERE cd.id = $1::uuid AND cd.customer_id = $2 AND cd.excluded = false""",
            document_id, session["customer_id"],
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Find or create an open customer_task for this document
        task = await conn.fetchrow(
            f"""SELECT id FROM {settings.database_app_schema}.customer_tasks
                WHERE document_id = $1::uuid AND customer_id = $2
                  AND status NOT IN ('completed', 'cancelled')
                ORDER BY created_at DESC LIMIT 1""",
            document_id, session["customer_id"],
        )
        if task:
            task_id = str(task["id"])
        else:
            task_id = str(_uuid.uuid4())
            await conn.execute(
                f"""INSERT INTO {settings.database_app_schema}.customer_tasks
                    (id, customer_id, plan_id, document_id, title, task_type, status, source,
                     requires_evidence, created_at, updated_at)
                    VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5, 'iso360_activity',
                            'pending', 'portal_evidence', TRUE, NOW(), NOW())""",
                task_id, session["customer_id"], str(doc["plan_id"]),
                document_id, doc["document_name"],
            )

    meta = await process_upload(file, session["customer_id"], task_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""UPDATE {settings.database_app_schema}.customer_tasks
                SET evidence_uploaded = true,
                    evidence_files = COALESCE(evidence_files, '[]'::jsonb) || $2::jsonb,
                    updated_at = NOW()
                WHERE id = $1::uuid""",
            task_id,
            _json.dumps([{
                "filename": meta["original_filename"],
                "path": meta["storage_path"],
                "source": "portal_iso360",
                "uploaded_at": __import__("datetime").datetime.utcnow().isoformat(),
            }]),
        )

    await log_activity("iso360_evidence_uploaded", session["token"], session["customer_id"],
                       detail={"document_id": document_id, "filename": meta["original_filename"],
                               "size": meta["size_bytes"]},
                       ip=request.client.host if request.client else None)
    return {"ok": True, "filename": meta["original_filename"], "task_id": task_id}


@router.post("/relink")
async def request_new_link(request: Request):
    """Customer requests a new token by email. Returns 200 regardless (no enumeration)."""
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        return {"ok": True}

    pool = await get_pool()
    async with pool.acquire() as conn:
        customer = await conn.fetchrow(
            f"""SELECT id FROM {settings.database_app_schema}.customers
                WHERE LOWER(email) = $1 OR LOWER(contact_email) = $1
                  OR LOWER(compliance_email) = $1 LIMIT 1""",
            email,
        )
    if customer:
        await log_activity("relink_requested", "none", customer["id"],
                           detail={"email": email},
                           ip=request.client.host if request.client else None)
    return {"ok": True}


# ── Help Me Answer ────────────────────────────────────────────────────────────

class HelpPayload(BaseModel):
    task_id: str


@router.post("/task-help")
async def task_help(payload: HelpPayload, session: dict = Depends(validate_token)):
    """Stream an AI explanation for a task using its template context."""
    from app.routes.chat import _get_llm_config
    from app.config import settings as cfg
    import json as _json

    # Load help-specific LLM config; fall back to chat config
    from app.db import get_pool as _get_pool
    _pool = await _get_pool()
    async with _pool.acquire() as _conn:
        _help_cfg = await _conn.fetchrow(
            f"SELECT provider, model FROM {settings.database_app_schema}.ai_config WHERE service = 'portal_help'"
        )
        _hl = await _conn.fetchrow(
            f"""SELECT config_value FROM {settings.database_app_schema}.customer_configuration
                WHERE customer_id IS NULL AND config_type = 'portal_help'
                  AND config_key = 'language' AND is_active = true LIMIT 1"""
        )
    help_language = (_hl["config_value"].strip('"') if _hl else None) or "en"

    llm_config = await _get_llm_config()
    if not llm_config:
        raise HTTPException(status_code=503, detail="No LLM provider configured")

    # Override with help-specific provider/model + its own API key if configured
    if _help_cfg and _help_cfg["provider"]:
        help_provider = _help_cfg["provider"]
        if help_provider != llm_config.get("provider"):
            # Different provider — fetch its own API key and decrypt
            _pool2 = await _get_pool()
            async with _pool2.acquire() as _conn2:
                _prov_row = await _conn2.fetchrow(
                    f"SELECT api_key FROM {settings.database_app_schema}.llm_providers WHERE name = $1 AND enabled = true",
                    help_provider,
                )
            if _prov_row and _prov_row["api_key"]:
                raw_key = _prov_row["api_key"]
                if raw_key.startswith("enc:"):
                    import base64, hashlib
                    from cryptography.fernet import Fernet
                    secret = settings.secret_key.encode()
                    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
                    raw_key = Fernet(fernet_key).decrypt(raw_key[4:].encode()).decode()
                llm_config = dict(llm_config)
                llm_config["provider"] = help_provider
                llm_config["model"] = _help_cfg["model"] or llm_config["model"]
                llm_config["api_key"] = raw_key
        else:
            # Same provider, just override model
            llm_config = dict(llm_config)
            llm_config["model"] = _help_cfg["model"] or llm_config["model"]

    # Fetch template context via MCP tool
    ctx: dict = {}
    try:
        from fastmcp import Client
        mcp_endpoint = f"{cfg.mcp_url}/mcp"
        async with Client(mcp_endpoint) as client:
            result = await client.call_tool(
                "get_template_context",
                {"token": session["token"], "task_id": payload.task_id},
            )
        items = result.content if hasattr(result, "content") else [result]
        raw = next((getattr(i, "text", None) or str(i) for i in items), "{}")
        ctx = _json.loads(raw) if raw.startswith("{") else {}
    except Exception as _mcp_err:
        import logging as _log
        _log.getLogger(__name__).warning(f"task-help MCP call failed: {_mcp_err}")

    # If MCP returned no question text, fall back to direct DB query for language detection
    if not ctx.get("question") and not ctx.get("section_content"):
        try:
            _pool = await _get_pool()
            async with _pool.acquire() as _conn:
                _row = await _conn.fetchrow(
                    f"""SELECT cp.question, cp.hint
                        FROM {settings.database_app_schema}.customer_tasks ct
                        LEFT JOIN {settings.database_app_schema}.customer_placeholders cp
                            ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
                        WHERE ct.id = $1::uuid AND ct.customer_id = $2""",
                    payload.task_id, session["customer_id"],
                )
            if _row:
                ctx.setdefault("question", _row["question"] or "")
                ctx.setdefault("hint", _row["hint"] or "")
        except Exception:
            pass

    # Build focused prompt
    # Auto-detect language from template content; fall back to configured language
    sample_text = ctx.get("question") or ctx.get("section_content") or ctx.get("hint") or ""
    if any('\u0590' <= c <= '\u05FF' for c in sample_text):
        lang_instruction = " Respond in Hebrew."
    elif help_language != "en":
        lang_instruction = f" Respond in language code: {help_language}."
    else:
        lang_instruction = ""

    system = (
        "You are an ISO compliance assistant helping a customer fill in their compliance documentation.\n"
        "You have been given the exact document, section, and ISO clause where this field appears.\n\n"
        "Respond with a JSON object containing exactly these four keys (translated to the response language):\n"
        "{\n"
        '  "based_on": "one sentence: [document name] · [section title] · [ISO clause] — what this section covers and why this field exists",\n'
        '  "what_this_asks": "1-2 sentences explaining what information is needed, referencing the document context",\n'
        '  "why_it_matters": "1-2 sentences on the ISO compliance significance",\n'
        '  "good_answer": "concrete practical guidance; reference the example value if provided"\n'
        "}\n\n"
        "Return ONLY the JSON object. No markdown, no code fences, no extra text.\n"
        f"Write all values in the same language as the question.{lang_instruction}"
    )
    parts = []
    if ctx.get("template_name"):
        parts.append(f"Document: {ctx['template_name']}")
    if ctx.get("iso_reference"):
        parts.append(f"ISO reference: {ctx['iso_reference']}")
    if ctx.get("section_title"):
        parts.append(f"Section: {ctx['section_title']}")
    if ctx.get("question"):
        parts.append(f"Question: {ctx['question']}")
    if ctx.get("hint"):
        parts.append(f"Hint: {ctx['hint']}")
    if ctx.get("example_value"):
        parts.append(f"Example: {ctx['example_value']}")
    if ctx.get("section_content"):
        parts.append(f"Section text:\n{ctx['section_content']}")
    if ctx.get("document_purpose"):
        parts.append(f"Document purpose:\n{ctx['document_purpose']}")

    user_msg = "\n".join(parts) if parts else f"Task ID: {payload.task_id}"

    provider = llm_config["provider"]
    model = llm_config["model"]
    api_key = llm_config["api_key"]

    print(f"[task-help] provider={provider}, model={model}, key_prefix={api_key[:8] if api_key else 'NONE'}...", flush=True)

    async def generate():
        import json as _j
        import datetime
        from app.routes.chat import _get_cost_rates, _log_usage

        # First event: grounding metadata for the frontend source card
        meta = {
            "type": "meta",
            "template_name": ctx.get("template_name") or "",
            "section_title": ctx.get("section_title") or "",
            "iso_reference": ctx.get("iso_reference") or "",
        }
        yield f"data: {_j.dumps(meta, ensure_ascii=False)}\n\n"

        tokens_in = tokens_out = 0
        started_at = datetime.datetime.now(datetime.timezone.utc)

        try:
            if provider in ("openai", "groq"):
                from openai import AsyncOpenAI
                from groq import AsyncGroq
                client = AsyncGroq(api_key=api_key) if provider == "groq" else AsyncOpenAI(api_key=api_key)
                kwargs = dict(
                    model=model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                    max_tokens=600, temperature=0.3, stream=True,
                )
                if provider == "openai":
                    kwargs["stream_options"] = {"include_usage": True}
                    kwargs["response_format"] = {"type": "json_object"}
                stream = await client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    token = chunk.choices[0].delta.content or "" if chunk.choices else ""
                    if token:
                        yield f"data: {token.replace(chr(10), '').replace(chr(13), '')}\n\n"
                    if chunk.usage:
                        tokens_in = chunk.usage.prompt_tokens or 0
                        tokens_out = chunk.usage.completion_tokens or 0

            elif provider in ("anthropic", "claude"):
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=api_key)
                async with client.messages.stream(
                    model=model, max_tokens=600, system=system,
                    messages=[{"role": "user", "content": user_msg}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield f"data: {text.replace(chr(10), '').replace(chr(13), '')}\n\n"
                    final = await stream.get_final_message()
                    tokens_in = final.usage.input_tokens or 0
                    tokens_out = final.usage.output_tokens or 0

            else:  # gemini
                from google import genai as _genai
                from google.genai import types as _genai_types
                _gclient = _genai.Client(api_key=api_key)
                async for chunk in await _gclient.aio.models.generate_content_stream(
                    model=model,
                    contents=user_msg,
                    config=_genai_types.GenerateContentConfig(system_instruction=system),
                ):
                    text = chunk.text or ""
                    if text:
                        yield f"data: {text.replace(chr(10), '').replace(chr(13), '')}\n\n"
                    if chunk.usage_metadata:
                        tokens_in = chunk.usage_metadata.prompt_token_count or 0
                        tokens_out = chunk.usage_metadata.candidates_token_count or 0

        except Exception as e:
            import traceback
            print(f"[task-help ERROR] provider={provider} model={model} err={e}", flush=True)
            print(traceback.format_exc(), flush=True)
            yield f"data: Sorry, I couldn't generate an explanation right now.\n\n"

        finally:
            yield "data: [DONE]\n\n"
            if tokens_in or tokens_out:
                duration_ms = int((datetime.datetime.now(datetime.timezone.utc) - started_at).total_seconds() * 1000)
                cost_rates = await _get_cost_rates(provider)
                await _log_usage(
                    session["customer_id"], provider, model,
                    tokens_in, tokens_out, cost_rates, started_at, duration_ms,
                    operation_type="portal_help",
                )

    return StreamingResponse(generate(), media_type="text/event-stream")
