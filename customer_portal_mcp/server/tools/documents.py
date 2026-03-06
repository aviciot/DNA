"""Tool: get_documents"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.tool(
    name="get_documents",
    description=(
        "List the customer's compliance documents with completion status.\n\n"
        "**Use when:** User asks which documents they need, how complete each document is, "
        "or wants an overview of their documentation requirements.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - plan_id: (optional) specific plan UUID\n"
        "**Returns:** list of documents with name, status, completion %, template info, due date"
    )
)
async def get_documents(token: str, plan_id: str = None):
    try:
        session = await validate_token(token)
        pid = plan_id or session["plan_id"]
        cid = session["customer_id"]

        rows = await db.fetch(
            """SELECT cd.id, cd.document_name, cd.document_type, cd.status,
                      cd.completion_percentage, cd.due_date,
                      t.name AS template_name, t.covered_clauses, t.covered_controls
               FROM dna_app.customer_documents cd
               LEFT JOIN dna_app.templates t ON t.id = cd.template_id
               WHERE cd.customer_id = $1 AND cd.plan_id = $2::uuid
               ORDER BY cd.completion_percentage ASC, cd.document_name""",
            cid, pid,
        )
        return {"documents": rows, "count": len(rows)}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"get_documents error: {e}")
        return {"error": "Failed to retrieve documents. Please try again."}
