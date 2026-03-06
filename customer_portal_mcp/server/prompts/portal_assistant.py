"""Prompt: portal_assistant — system prompt loaded from ai_prompts DB table"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.prompt(
    name="portal_assistant",
    description="System prompt for the customer compliance assistant. Loads from DB, interpolates customer context."
)
async def portal_assistant(token: str) -> str:
    """
    Returns the fully-rendered system prompt for this customer's session.
    Loads prompt template from ai_prompts table (prompt_key='portal_mcp_system').
    Interpolates: customer_name, iso_name, language, pending_count.
    """
    try:
        session = await validate_token(token)
        cid = session["customer_id"]
        pid = session["plan_id"]

        # Load prompt template from DB
        prompt_row = await db.fetchrow(
            "SELECT prompt_text FROM dna_app.ai_prompts WHERE prompt_key = 'portal_mcp_system' AND is_active = true LIMIT 1"
        )
        if not prompt_row:
            # Fallback hardcoded prompt if DB row missing
            prompt_template = (
                "You are a friendly ISO compliance assistant for {customer_name}, "
                "helping them complete their {iso_name} certification.\n\n"
                "RULES:\n"
                "- Always respond in {language}\n"
                "- Only discuss tasks, documents, and questions related to this customer's compliance plan\n"
                "- Never invent information — only use data returned by tools\n"
                "- Never discuss other customers or unrelated topics\n"
                "- Current status: {pending_count} tasks pending\n"
                "- Be encouraging and explain WHY each question matters for ISO compliance\n"
                "- If asked off-topic, respond in {language}: "
                "\"I can only help with your {iso_name} compliance tasks\""
            )
        else:
            prompt_template = prompt_row["prompt_text"]

        # Get pending count
        pending_row = await db.fetchrow(
            """SELECT COUNT(*) AS pending FROM dna_app.customer_tasks
               WHERE customer_id = $1 AND plan_id = $2::uuid
                 AND status = 'pending' AND is_ignored = false""",
            cid, pid,
        )
        pending_count = pending_row["pending"] if pending_row else 0

        return prompt_template.format(
            customer_name=session["customer_name"],
            iso_name=session["iso_name"],
            iso_code=session["iso_code"],
            plan_name=session["plan_name"],
            language=session["language"],
            pending_count=pending_count,
        )

    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.exception(f"portal_assistant prompt error: {e}")
        return "You are a compliance assistant. Only discuss the customer's ISO compliance tasks."
