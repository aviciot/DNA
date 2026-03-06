"""Tool: get_progress"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.tool(
    name="get_progress",
    description=(
        "Get the customer's ISO compliance progress.\n\n"
        "**Use when:** User asks how far along they are, what's left, or wants a summary.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - plan_id: (optional) specific plan UUID; defaults to token's plan\n"
        "**Returns:** total/completed/pending task counts, percentage, target date, plan info"
    )
)
async def get_progress(token: str, plan_id: str = None):
    try:
        session = await validate_token(token)
        pid = plan_id or session["plan_id"]
        cid = session["customer_id"]

        row = await db.fetchrow(
            """SELECT
                COUNT(*) FILTER (WHERE is_ignored = false) AS total,
                COUNT(*) FILTER (WHERE status IN ('completed','answered') AND is_ignored = false) AS completed,
                COUNT(*) FILTER (WHERE status = 'pending' AND is_ignored = false) AS pending,
                COUNT(*) FILTER (WHERE requires_evidence = true AND evidence_uploaded = false AND is_ignored = false) AS evidence_pending
               FROM dna_app.customer_tasks
               WHERE customer_id = $1 AND plan_id = $2::uuid""",
            cid, pid,
        )
        total = row["total"] or 0
        completed = row["completed"] or 0
        return {
            "customer_name": session["customer_name"],
            "plan_name": session["plan_name"],
            "iso_name": session["iso_name"],
            "total": total,
            "completed": completed,
            "pending": row["pending"] or 0,
            "evidence_pending": row["evidence_pending"] or 0,
            "percentage": round(completed / total * 100) if total else 0,
        }
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"get_progress error: {e}")
        return {"error": "Failed to retrieve progress. Please try again."}
