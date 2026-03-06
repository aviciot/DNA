"""Resource: context://customer/{token} — full customer snapshot"""
import json
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.resource("context://customer/{token}")
async def get_portal_context(token: str) -> str:
    """
    Full snapshot of the customer's compliance state.
    Read this at session start to have complete context before the first message.
    Includes: customer info, progress, top pending tasks with questions, documents, already-collected answers.
    """
    try:
        session = await validate_token(token)
        cid = session["customer_id"]
        pid = session["plan_id"]

        # Progress
        progress = await db.fetchrow(
            """SELECT
                COUNT(*) FILTER (WHERE is_ignored = false) AS total,
                COUNT(*) FILTER (WHERE status IN ('completed','answered') AND is_ignored = false) AS completed,
                COUNT(*) FILTER (WHERE status = 'pending' AND is_ignored = false) AS pending,
                COUNT(*) FILTER (WHERE requires_evidence = true AND evidence_uploaded = false AND is_ignored = false) AS evidence_pending
               FROM dna_app.customer_tasks
               WHERE customer_id = $1 AND plan_id = $2::uuid""",
            cid, pid,
        )

        # Top 20 pending tasks with question context
        tasks = await db.fetch(
            """SELECT ct.id, ct.title, ct.status, ct.priority,
                      ct.placeholder_key, ct.due_date, ct.requires_evidence,
                      cp.question, cp.hint, cp.category
               FROM dna_app.customer_tasks ct
               LEFT JOIN dna_app.customer_placeholders cp
                 ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
               WHERE ct.customer_id = $1 AND ct.plan_id = $2::uuid
                 AND ct.is_ignored = false AND ct.status = 'pending'
               ORDER BY
                   CASE ct.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
               LIMIT 20""",
            cid, pid,
        )

        # Documents
        docs = await db.fetch(
            """SELECT cd.document_name, cd.status, cd.completion_percentage
               FROM dna_app.customer_documents cd
               WHERE cd.customer_id = $1 AND cd.plan_id = $2::uuid
               ORDER BY cd.completion_percentage ASC""",
            cid, pid,
        )

        # Already-collected profile data
        profile = await db.fetch(
            """SELECT field_key, field_value, display_label
               FROM dna_app.customer_profile_data
               WHERE customer_id = $1
               ORDER BY field_key""",
            cid,
        )

        total = progress["total"] or 0
        completed = progress["completed"] or 0

        snapshot = {
            "customer_name": session["customer_name"],
            "iso_code": session["iso_code"],
            "iso_name": session["iso_name"],
            "plan_name": session["plan_name"],
            "language": session["language"],
            "progress": {
                "total": total,
                "completed": completed,
                "pending": progress["pending"] or 0,
                "evidence_pending": progress["evidence_pending"] or 0,
                "percentage": round(completed / total * 100) if total else 0,
            },
            "pending_tasks": tasks,
            "documents": docs,
            "collected_answers": {r["field_key"]: r["field_value"] for r in profile},
        }
        return json.dumps(snapshot, default=str, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.exception(f"portal_context error: {e}")
        return json.dumps({"error": "Failed to load context."})
