"""Tool: log_llm_usage — tracks LLM usage per customer into ai_usage_log"""
import logging
from datetime import datetime, timezone
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


@mcp.tool(
    name="log_llm_usage",
    description=(
        "Log LLM usage for a customer chat turn. Call this after each AI response.\n\n"
        "**Use when:** After every LLM call made on behalf of a customer.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - provider: LLM provider name (e.g. gemini, anthropic)\n"
        "  - model: Model name used\n"
        "  - tokens_input: Input token count\n"
        "  - tokens_output: Output token count\n"
        "  - cost_usd: Cost in USD (0 if unknown)\n"
        "  - operation: Description (default: portal_chat)\n"
        "**Returns:** {ok: true}"
    )
)
async def log_llm_usage(
    token: str,
    provider: str,
    model: str,
    tokens_input: int,
    tokens_output: int,
    cost_usd: float = 0.0,
    operation: str = "portal_chat",
):
    try:
        session = await validate_token(token)
        cid = session["customer_id"]
        now = datetime.now(timezone.utc)

        await db.execute(
            """INSERT INTO dna_app.ai_usage_log
                 (operation_type, customer_id, provider, model, tokens_input, tokens_output,
                  cost_usd, status, started_at, completed_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'success', $8, $8)""",
            operation, cid, provider, model, tokens_input, tokens_output,
            cost_usd, now,
        )
        return {"ok": True}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"log_llm_usage error: {e}")
        return {"error": "Failed to log usage."}
