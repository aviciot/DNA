"""Tool: get_template_context"""
import logging
from mcp_app import mcp
from tools.auth import validate_token
from db.connector import db

logger = logging.getLogger(__name__)


def _find_section_for_key(structure: dict, placeholder_key: str) -> dict | None:
    """Walk sections and subsections to find the one containing {{placeholder_key}}."""
    marker = f"{{{{{placeholder_key}}}}}"
    for section in structure.get("sections", []):
        content = section.get("content") or ""
        if marker in content:
            return section
        for sub in section.get("subsections", []):
            sub_content = sub.get("content") or ""
            if marker in sub_content:
                # Return the subsection enriched with parent title
                return {**sub, "_parent_title": section.get("title", "")}
    return None


def _find_purpose_section(structure: dict) -> str:
    """Return content of the first section whose title suggests purpose/scope."""
    keywords = ("purpose", "scope", "introduction", "overview")
    for section in structure.get("sections", []):
        title = (section.get("title") or "").lower()
        if any(k in title for k in keywords):
            return (section.get("content") or "")[:500]
    return ""


@mcp.tool(
    name="get_template_context",
    description=(
        "Get rich template context for a task to help explain what the question is asking.\n\n"
        "**Use when:** User asks for help understanding a task or what they need to provide.\n"
        "**Parameters:**\n"
        "  - token: Portal authentication token\n"
        "  - task_id: UUID of the task\n"
        "**Returns:** Section text, ISO reference, question, hint, and document purpose."
    )
)
async def get_template_context(token: str, task_id: str):
    try:
        session = await validate_token(token)
        cid = session["customer_id"]

        row = await db.fetchrow(
            """SELECT ct.placeholder_key, ct.template_id, ct.plan_id,
                      t.name AS template_name, t.template_structure,
                      cp.question, cp.hint, cp.example_value
               FROM dna_app.customer_tasks ct
               LEFT JOIN dna_app.templates t ON t.id = ct.template_id
               LEFT JOIN dna_app.customer_placeholders cp
                   ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
               WHERE ct.id = $1::uuid AND ct.customer_id = $2""",
            task_id, cid,
        )
        if not row:
            return {"error": "Task not found."}

        placeholder_key = row["placeholder_key"] or ""
        structure = row["template_structure"] or {}
        if isinstance(structure, str):
            import json
            structure = json.loads(structure)

        section = _find_section_for_key(structure, placeholder_key) if placeholder_key else None
        if not section and structure.get("sections"):
            # Fallback: use first non-metadata section
            for s in structure["sections"]:
                if s.get("content"):
                    section = s
                    break

        return {
            "placeholder_key": placeholder_key,
            "question": row["question"] or "",
            "hint": row["hint"] or "",
            "example_value": row["example_value"] or "",
            "iso_reference": section.get("iso_reference", "") if section else "",
            "section_title": section.get("title", "") if section else "",
            "section_content": (section.get("content") or "")[:1000] if section else "",
            "document_purpose": _find_purpose_section(structure),
            "template_name": row["template_name"] or "",
        }
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"get_template_context error: {e}")
        return {"error": "Failed to fetch template context."}
