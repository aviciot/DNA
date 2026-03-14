"""
ISO360 KYC Summary Agent
========================
Synthesises a customer's KYC answers into a structured profile + Mermaid graph.

One call per customer × plan (not per template).
Result is stored in iso360_kyc_batches and reused for all template adjustments.
"""
import json
import logging
import re
from typing import Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_FALLBACK_SUMMARY = {
    "org_profile": {
        "size": "unknown",
        "industry": "unknown",
        "cloud": [],
        "key_tools": [],
        "dev_stack": [],
    },
    "existing_controls": [],
    "identified_gaps": [],
    "compliance_maturity": "unknown",
    "key_risks": [],
}

_FALLBACK_GRAPH = 'graph LR\n  ORG["Organisation"]\n  ORG --> INFO["KYC answers not yet processed"]'


class ISO360SummaryAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "ISO360SummaryAgent"

    async def generate_summary(
        self,
        kyc_answers: str,
        customer_name: str,
        industry: str,
        company_size: str,
        iso_code: str,
        system_prompt: str,
        user_template: str,
        trace_id: Optional[str] = None,
    ) -> tuple[dict, str]:
        """
        Returns (summary_dict, mermaid_graph_str).
        Falls back to static defaults on any LLM failure.
        """
        variables = {
            "customer_name": customer_name or "Unknown",
            "industry":      industry or "Unknown",
            "company_size":  company_size or "Unknown",
            "iso_code":      iso_code or "ISO",
            "kyc_answers":   kyc_answers or "(no answers available)",
        }

        user_prompt = user_template
        for k, v in variables.items():
            user_prompt = user_prompt.replace(f"{{{{{k}}}}}", str(v))

        try:
            result = await self._call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                trace_id=trace_id,
                call_purpose="iso360_kyc_summary",
            )
            raw = result.get("content", "")
            parsed = _parse_json_response(raw)

            if not parsed or not isinstance(parsed, dict):
                raise ValueError(f"LLM returned invalid JSON: {raw[:300]!r}")

            summary = parsed.get("summary")
            graph   = parsed.get("graph", "").strip()

            if not isinstance(summary, dict):
                raise ValueError("LLM response missing 'summary' key")
            if not graph:
                graph = _FALLBACK_GRAPH

            logger.info(
                f"ISO360SummaryAgent: summary generated for {customer_name!r} "
                f"({iso_code}), maturity={summary.get('compliance_maturity')}"
            )
            return summary, graph

        except Exception as e:
            logger.warning(f"ISO360SummaryAgent: LLM call failed: {e} — using fallback")
            return _FALLBACK_SUMMARY, _FALLBACK_GRAPH


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {}


def format_summary_for_prompt(summary: dict) -> str:
    """Convert the structured summary dict to a compact string for the adjustment prompt."""
    if not summary or summary == _FALLBACK_SUMMARY:
        return "(no customer profile available)"

    org = summary.get("org_profile", {})
    lines = [
        f"Organisation: {org.get('industry', 'unknown')}, {org.get('size', 'unknown')}",
    ]
    if org.get("cloud"):
        lines.append(f"Cloud: {', '.join(org['cloud'])}")
    if org.get("key_tools"):
        lines.append(f"Key tools: {', '.join(org['key_tools'])}")
    if org.get("dev_stack"):
        lines.append(f"Tech stack: {', '.join(org['dev_stack'])}")
    if summary.get("existing_controls"):
        lines.append("Existing controls: " + "; ".join(summary["existing_controls"]))
    if summary.get("identified_gaps"):
        lines.append("Gaps: " + "; ".join(summary["identified_gaps"]))
    if summary.get("key_risks"):
        lines.append("Key risks: " + "; ".join(summary["key_risks"]))
    maturity = summary.get("compliance_maturity")
    if maturity:
        lines.append(f"Compliance maturity: {maturity}")

    return "\n".join(lines)
