"""
ISO360 Adjustment Agent
=======================
Personalises a platform-level ISO360 template with the customer's actual
context (their systems, tools, and collected answers) so the resulting
customer_document reflects the organisation's real environment.

Falls back to the original template on any LLM failure — the job must
never crash; a non-personalised copy is always better than a missing one.
"""
import json
import logging

logger = logging.getLogger(__name__)


async def adjust_iso360_template(
    placeholder_key: str,
    template_steps: list,
    evidence_fields: list,
    customer_answers: str,
    customer_industry: str,
    customer_size: str,
    ai_config: dict,        # {provider, model, _api_key}
    settings,
    ai_prompt_getter,       # async callable: get_ai_prompt(key) -> dict|None
) -> dict:
    """
    Personalise an ISO360 template for a specific customer.

    Returns a dict: {title, responsible_role, steps, evidence_fields}
    where steps and evidence_fields have been adjusted to reference the
    customer's actual systems, tools, and processes.

    Falls back to the original template values on any LLM failure.
    """
    fallback = {
        "steps": template_steps,
        "evidence_fields": evidence_fields,
    }

    system_row = await ai_prompt_getter("iso360_adjustment_system")
    user_row   = await ai_prompt_getter("iso360_adjustment_user")

    if not system_row or not user_row:
        logger.warning(
            f"ISO360 adjustment agent: prompts not found, using original template for {placeholder_key!r}"
        )
        return fallback

    system_prompt = system_row["prompt_text"]
    user_template = user_row["prompt_text"]
    model = ai_config.get("model") or "gemini-2.5-flash"

    # Format steps and evidence_fields as readable JSON for the prompt
    steps_text   = json.dumps(template_steps, ensure_ascii=False, indent=2)
    ev_text      = json.dumps(evidence_fields, ensure_ascii=False, indent=2)

    variables = {
        "template_steps":    steps_text,
        "evidence_fields":   ev_text,
        "customer_answers":  customer_answers or "(no answers collected yet)",
        "customer_industry": customer_industry or "unknown",
        "customer_size":     customer_size or "unknown",
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
        result = _parse_json_response(raw)

        if not result or not isinstance(result, dict):
            raise ValueError(f"LLM returned empty/invalid JSON for {placeholder_key!r}: {raw[:200]!r}")

        # Validate required keys — fall back if either is missing or malformed
        adj_steps = result.get("steps")
        adj_ev    = result.get("evidence_fields")

        if not isinstance(adj_steps, list) or not isinstance(adj_ev, list):
            raise ValueError(
                f"LLM response missing steps/evidence_fields for {placeholder_key!r}"
            )

        return {
            "steps":          adj_steps,
            "evidence_fields": adj_ev,
        }

    except Exception as e:
        logger.warning(
            f"ISO360 adjustment agent: LLM call failed for {placeholder_key!r}: {e} — "
            f"using original template"
        )
        return fallback
