"""
ISO360 Adjustment Agent
=======================
Personalises a platform-level ISO360 template with the customer's actual
context (their systems, tools, and collected answers) so the resulting
customer_document reflects the organisation's real environment.

Adapted from automation-service to use BaseAgent pattern.
Falls back to the original template on any LLM failure — the job must
never crash; a non-personalised copy is always better than a missing one.
"""
import json
import logging
from typing import Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ISO360AdjustmentAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "ISO360AdjustmentAgent"

    async def adjust_iso360_template(
        self,
        placeholder_key: str,
        template_steps: list,
        evidence_fields: list,
        customer_answers: str,
        customer_industry: str,
        customer_size: str,
        system_prompt: str,
        user_template: str,
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Personalise an ISO360 template for a specific customer.

        Returns a dict: {steps, evidence_fields} where steps and evidence_fields
        have been adjusted to reference the customer's actual systems, tools, and processes.

        Falls back to the original template values on any LLM failure.

        Args:
            placeholder_key: The ISO360 placeholder key (for logging)
            template_steps: Original template steps list
            evidence_fields: Original evidence fields list
            customer_answers: Formatted string of customer answers for context
            customer_industry: Customer's industry string
            customer_size: Customer's company size string
            system_prompt: System prompt text from ai_prompts
            user_template: User prompt template text from ai_prompts
            trace_id: Optional trace ID for telemetry
        """
        fallback = {
            "steps": template_steps,
            "evidence_fields": evidence_fields,
        }

        # Format steps and evidence_fields as readable JSON for the prompt
        steps_text = json.dumps(template_steps, ensure_ascii=False, indent=2)
        ev_text    = json.dumps(evidence_fields, ensure_ascii=False, indent=2)

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
            result = await self._call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                trace_id=trace_id,
                call_purpose="iso360_adjustment",
            )
            raw = result.get("content", "")
            adjusted = _parse_json_response(raw)

            if not adjusted or not isinstance(adjusted, dict):
                raise ValueError(
                    f"LLM returned empty/invalid JSON for {placeholder_key!r}: {raw[:200]!r}"
                )

            # Validate required keys — fall back if either is missing or malformed
            adj_steps = adjusted.get("steps")
            adj_ev    = adjusted.get("evidence_fields")

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
                f"ISO360AdjustmentAgent: LLM call failed for {placeholder_key!r}: {e} — "
                f"using original template"
            )
            return fallback


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
