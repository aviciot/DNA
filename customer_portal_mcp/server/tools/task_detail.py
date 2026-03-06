"""Tool: get_task_detail — full context for a single task including template and document info"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.tool(
    name="get_task_detail",
    description=(
        "Get full details for a specific task including which document it belongs to, "
        "which ISO clause it covers, the question text, hint, and example answer.\n\n"
        "**Use when:** User asks about a specific task, wants to understand what a question means, "
        "or needs guidance on how to answer it.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - task_id: UUID of the task\n"
        "**Returns:** full task context — document name, ISO clauses, question, hint, example, current answer"
    )
)
async def get_task_detail(token: str, task_id: str):
    try:
        session = await validate_token(token)
        cid = session["customer_id"]

        row = await db.fetchrow(
            """SELECT ct.id, ct.title, ct.description, ct.status, ct.priority,
                      ct.placeholder_key, ct.due_date, ct.requires_evidence,
                      ct.evidence_uploaded, ct.evidence_description, ct.answer,
                      ct.answered_at, ct.answered_via,
                      cp.question, cp.hint, cp.example_value, cp.category, cp.semantic_tags,
                      t.name AS template_name, t.description AS template_description,
                      t.covered_clauses, t.covered_controls,
                      cd.document_name, cd.completion_percentage, cd.status AS document_status
               FROM dna_app.customer_tasks ct
               LEFT JOIN dna_app.customer_placeholders cp
                 ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
               LEFT JOIN dna_app.templates t ON t.id = ct.template_id
               LEFT JOIN dna_app.customer_documents cd ON cd.id = ct.document_id
               WHERE ct.id = $1::uuid AND ct.customer_id = $2""",
            task_id, cid,
        )
        if not row:
            return {"error": "Task not found."}
        return dict(row)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"get_task_detail error: {e}")
        return {"error": "Failed to retrieve task details. Please try again."}
