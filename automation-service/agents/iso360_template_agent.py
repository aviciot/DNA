"""
ISO360 Template Agent
=====================
Generates a structured task/evidence template for a recurring ISO360 placeholder
using the iso360_template_system / iso360_template_user prompts from ai_prompts.

Falls back to a minimal static template if the LLM fails — generation must
never crash the job; a fallback template is always better than a gap.
"""
import logging

logger = logging.getLogger(__name__)


async def generate_iso360_template(
    placeholder_key: str,
    type_: str,
    update_frequency: str,
    iso_clause: str,
    category: str,
    iso_standard_name: str,
    ai_config: dict,        # {provider, model, _api_key} from get_ai_config_for_service()
    settings,
    ai_prompt_getter,       # async callable: get_ai_prompt(key) -> dict|None
    description: str = "",
) -> dict:
    """
    Returns a template dict: {title, responsible_role, steps, evidence_fields}.
    Falls back to a minimal static template on any LLM failure.
    """
    system_row = await ai_prompt_getter("iso360_template_system")
    user_row   = await ai_prompt_getter("iso360_template_user")

    if not system_row or not user_row:
        logger.warning(f"ISO360 template agent: prompts not found, using fallback for {placeholder_key!r}")
        return _fallback(placeholder_key)

    system_prompt = system_row["prompt_text"]
    user_template = user_row["prompt_text"]
    model = ai_config.get("model") or "gemini-2.5-flash"

    variables = {
        "placeholder_key":   placeholder_key,
        "type":              type_,
        "update_frequency":  update_frequency,
        "iso_clause":        iso_clause or "",
        "category":          category or "",
        "iso_standard_name": iso_standard_name,
        "description":       description or "",
    }
    user_prompt = user_template
    for k, v in variables.items():
        user_prompt = user_prompt.replace(f"{{{{{k}}}}}", str(v) if v else "")

    try:
        from agents.notification_email_agent import _call_llm, _parse_json_response
        cfg = {
            "llm_provider": ai_config.get("provider", "gemini"),
            "_api_key":     ai_config.get("_api_key", ""),
        }
        raw = await _call_llm(system_prompt, user_prompt, model, 0.3, cfg, settings)
        tmpl = _parse_json_response(raw)

        if not tmpl or "steps" not in tmpl:
            raise ValueError(f"LLM response missing 'steps': {raw[:200]!r}")

        steps = tmpl.get("steps", [])
        evidence_fields = tmpl.get("evidence_fields", [])
        title = tmpl.get("title") or _make_title(placeholder_key)
        responsible_role = tmpl.get("responsible_role") or "Compliance Manager"

        return {
            "title":            title,
            "responsible_role": responsible_role,
            "steps":            steps if isinstance(steps, list) else [],
            "evidence_fields":  evidence_fields if isinstance(evidence_fields, list) else [],
        }

    except Exception as e:
        logger.warning(f"ISO360 template agent: LLM call failed for {placeholder_key!r}: {e}")
        return _fallback(placeholder_key)


def _make_title(placeholder_key: str) -> str:
    return placeholder_key.replace("_", " ").title()


def _fallback(placeholder_key: str) -> dict:
    title = _make_title(placeholder_key)
    return {
        "title":            title,
        "responsible_role": "Compliance Manager",
        "steps": [
            {"order": 1, "instruction": f"Review current state of {title.lower()}"},
            {"order": 2, "instruction": "Document findings and update relevant records"},
            {"order": 3, "instruction": "Obtain required approvals and sign-offs"},
        ],
        "evidence_fields": [
            {"field_name": "review_date",    "field_type": "date",    "required": True},
            {"field_name": "reviewer_name",  "field_type": "text",    "required": True},
            {"field_name": "notes",          "field_type": "text",    "required": False},
        ],
    }
