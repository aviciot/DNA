"""Tool: submit_answer"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.tool(
    name="submit_answer",
    description=(
        "Submit an answer for a compliance task.\n\n"
        "**Use when:** User provides an answer to a question and wants to save it.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - task_id: UUID of the task\n"
        "  - placeholder_key: The placeholder key for this task\n"
        "  - value: The answer text\n"
        "**Returns:** {ok: true} on success"
    )
)
async def submit_answer(token: str, task_id: str, placeholder_key: str, value: str):
    try:
        session = await validate_token(token)
        cid = session["customer_id"]

        # Verify task belongs to this customer
        task = await db.fetchrow(
            """SELECT id FROM dna_app.customer_tasks
               WHERE id = $1::uuid AND customer_id = $2 AND status != 'cancelled'""",
            task_id, cid,
        )
        if not task:
            return {"error": "Task not found."}

        await db.execute(
            """UPDATE dna_app.customer_tasks
               SET answer = $2, answered_via = 'portal_mcp', answered_at = NOW(),
                   status = CASE WHEN status = 'pending' THEN 'answered' ELSE status END,
                   updated_at = NOW()
               WHERE id = $1::uuid""",
            task_id, value,
        )
        await db.execute(
            """INSERT INTO dna_app.customer_profile_data
                 (customer_id, field_key, field_value, source, filled_via, filled_at)
               VALUES ($1, $2, $3, 'portal_mcp', 'portal_mcp', NOW())
               ON CONFLICT (customer_id, field_key) DO UPDATE
               SET field_value = EXCLUDED.field_value,
                   filled_via = 'portal_mcp',
                   filled_at = NOW(),
                   updated_at = NOW()""",
            cid, placeholder_key, value,
        )
        return {"ok": True}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"submit_answer error: {e}")
        return {"error": "Failed to save answer. Please try again."}
