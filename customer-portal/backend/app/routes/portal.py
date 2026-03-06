from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.db import get_pool, validate_token, log_activity
from app.upload import process_upload

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

    await log_activity("token_validated", token, row["customer_id"],
                       ip=request.client.host if request.client else None)

    response = RedirectResponse(url="/portal")
    response.set_cookie(
        key="portal_token",
        value=token,
        httponly=True,
        secure=False,  # set True in production behind HTTPS
        samesite="strict",
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
        # Verify task belongs to this customer/plan
        task = await conn.fetchrow(
            f"""SELECT id FROM {settings.database_app_schema}.customer_tasks
                WHERE id = $1::uuid AND customer_id = $2 AND plan_id = $3
                  AND status != 'cancelled'""",
            payload.task_id, session["customer_id"], session["plan_id"],
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        await conn.execute(
            f"""UPDATE {settings.database_app_schema}.customer_tasks
                SET answer = $2, answered_via = 'portal', answered_at = NOW(),
                    status = CASE WHEN status = 'pending' THEN 'answered' ELSE status END,
                    updated_at = NOW()
                WHERE id = $1::uuid""",
            payload.task_id, payload.value,
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
                WHERE id = $1::uuid AND customer_id = $2 AND plan_id = $3
                  AND requires_evidence = true AND status != 'cancelled'""",
            task_id, session["customer_id"], session["plan_id"],
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
                    status = CASE WHEN status = 'pending' THEN 'answered' ELSE status END,
                    answered_via = 'portal', answered_at = NOW(), updated_at = NOW()
                WHERE id = $1::uuid""",
            task_id,
            json.dumps([{
                "filename": meta["original_filename"],
                "path": meta["storage_path"],
                "source": "portal",
                "uploaded_at": __import__("datetime").datetime.utcnow().isoformat(),
            }]),
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
        # TODO: trigger automation-service to send a new token email
        # For now just log the request
        await log_activity("relink_requested", "none", customer["id"],
                           detail={"email": email},
                           ip=request.client.host if request.client else None)
    return {"ok": True}
