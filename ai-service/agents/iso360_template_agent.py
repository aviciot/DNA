"""
ISO360 Template Agent
=====================
Generates a structured task/evidence template for a recurring ISO360 placeholder
using the iso360_template_system / iso360_template_user prompts from ai_prompts.

Adapted from automation-service to use BaseAgent pattern.
Falls back to a minimal static template if the LLM fails — generation must
never crash the job; a fallback template is always better than a gap.
"""
import json
import logging
from typing import Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ISO360TemplateAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "ISO360TemplateAgent"

    async def generate_iso360_template(
        self,
        placeholder_key: str,
        type_: str,
        update_frequency: str,
        iso_clause: str,
        category: str,
        iso_standard_name: str,
        system_prompt: str,
        user_template: str,
        description: str = "",
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Generate a template dict: {title, responsible_role, steps, evidence_fields}.
        Falls back to a minimal static template on any LLM failure.

        Args:
            placeholder_key: The ISO360 placeholder key (e.g. 'access_review')
            type_: Activity type (e.g. 'review', 'operational_activity', 'record')
            update_frequency: 'monthly', 'quarterly', 'yearly', or 'event_based'
            iso_clause: ISO clause reference (e.g. 'A.9.2')
            category: Template category / activity category
            iso_standard_name: Full name of the ISO standard
            system_prompt: System prompt text from ai_prompts
            user_template: User prompt template text from ai_prompts
            description: Optional description of the activity
            trace_id: Optional trace ID for telemetry
        """
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
            result = await self._call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                trace_id=trace_id,
                call_purpose="iso360_template_generation",
            )
            raw = result.get("content", "")
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
            logger.warning(
                f"ISO360TemplateAgent: LLM call failed for {placeholder_key!r}: {e} — using fallback"
            )
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


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # Try to find JSON object in the text
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {}
