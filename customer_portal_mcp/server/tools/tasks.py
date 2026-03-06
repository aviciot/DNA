"""Tool: get_tasks"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.tool(
    name="get_tasks",
    description=(
        "List the customer's compliance tasks with question text and hints.\n\n"
        "**Use when:** User wants to see their tasks, what questions they need to answer, or filter by status/priority.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - plan_id: (optional) specific plan UUID\n"
        "  - status_filter: (optional) pending | answered | completed | all (default: all)\n"
        "  - priority_filter: (optional) urgent | high | medium | low\n"
        "**Returns:** list of tasks with question text, hint, category, status, priority"
    )
)
async def get_tasks(token: str, plan_id: str = None, status_filter: str = "all", priority_filter: str = None):
    try:
        session = await validate_token(token)
        pid = plan_id or session["plan_id"]
        cid = session["customer_id"]

        conditions = ["ct.customer_id = $1", "ct.plan_id = $2::uuid",
                      "ct.is_ignored = false", "ct.status != 'cancelled'"]
        params = [cid, pid]

        if status_filter and status_filter != "all":
            params.append(status_filter)
            conditions.append(f"ct.status = ${len(params)}")

        if priority_filter:
            params.append(priority_filter)
            conditions.append(f"ct.priority = ${len(params)}")

        where = " AND ".join(conditions)
        rows = await db.fetch(
            f"""SELECT ct.id, ct.title, ct.description, ct.status, ct.priority,
                       ct.placeholder_key, ct.due_date, ct.requires_evidence,
                       ct.evidence_uploaded, ct.answer,
                       cp.question, cp.hint, cp.category, cp.example_value
                FROM dna_app.customer_tasks ct
                LEFT JOIN dna_app.customer_placeholders cp
                  ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
                WHERE {where}
                ORDER BY
                    CASE ct.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                    ct.created_at""",
            *params,
        )
        return {"tasks": rows, "count": len(rows)}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"get_tasks error: {e}")
        return {"error": "Failed to retrieve tasks. Please try again."}
