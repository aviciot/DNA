"""
Email Extraction Agent
======================
Uses the configured LLM provider (Claude / Gemini / Groq) to:
  1. Extract answers to pending questions from email body
  2. Match attachments to open evidence tasks

Returns structured list of extraction items with confidence scores.
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a compliance data extraction assistant.
Your job is to read customer email replies and extract answers to specific compliance questions.
You MUST respond with valid JSON only — no markdown, no explanation outside the JSON.

Two rules for confidence scoring:
1. If the customer clearly and specifically answers a question → confidence 0.85–1.0 (auto-apply)
2. If the customer provides ANY direct response to a question, even vague or incomplete → confidence 0.40–0.70 (human review)
   Do NOT silently drop vague answers — extract them with low confidence so a human can decide.

Only omit a question entirely when the email has zero relevant content for it.
If the customer asks a question rather than answering, add its key to follow_up_keys.
Questions marked [ANSWERED] already have an answer on file — only extract if the new answer is different or more specific."""

EXTRACTION_PROMPT = """
## Compliance Questions to Answer

{questions_block}

## Evidence / Document Requests

{evidence_block}

## Customer Email Body

{body_text}

## Attachments

{attachments_block}

---

Extract answers and evidence matches. Return ONLY this JSON:

{{
  "answers": [
    {{
      "placeholder_key": "the_key",
      "value": "extracted answer text",
      "confidence": 0.95,
      "reasoning": "Customer stated this directly in paragraph 2"
    }}
  ],
  "evidence_matches": [
    {{
      "task_id": "uuid-of-task",
      "filename": "attached_file.pdf",
      "confidence": 0.80,
      "reasoning": "Filename and content matches the requested ISO certificate"
    }}
  ],
  "follow_up_keys": ["key1", "key2"],
  "notes": "Optional: anything else useful from this email"
}}

Rules:
- confidence must be between 0.0 and 1.0
- Only include items you actually found — do not fabricate
- For questions with no answer in the email, omit them entirely from "answers"
- For evidence: match by filename AND content description
"""


def _build_questions_block(questions: list) -> str:
    if not questions:
        return "(none)"
    lines = []
    for i, q in enumerate(questions, 1):
        key = q.get("placeholder_key", "")
        question = q.get("question", key)
        hint = q.get("hint", "")
        status = q.get("status", "pending")
        current_answer = q.get("current_answer")
        already_done = status in ("answered", "completed")
        tag = " [ANSWERED]" if already_done else ""
        lines.append(f"{i}. Key: `{key}`{tag}")
        lines.append(f"   Question: {question}")
        if hint:
            lines.append(f"   Hint: {hint}")
        if already_done and current_answer:
            lines.append(f"   Current answer on file: {current_answer}")
    return "\n".join(lines)


def _build_evidence_block(evidence_tasks: list) -> str:
    if not evidence_tasks:
        return "(none)"
    lines = []
    for i, ev in enumerate(evidence_tasks, 1):
        lines.append(f"{i}. Task ID: {ev.get('task_id','')}")
        lines.append(f"   Title: {ev.get('title','')}")
        if ev.get("description"):
            lines.append(f"   Description: {ev['description']}")
    return "\n".join(lines)


def _build_attachments_block(parsed_attachments: list) -> str:
    if not parsed_attachments:
        return "(no attachments)"
    lines = []
    for att in parsed_attachments:
        lines.append(f"Filename: {att['filename']} ({att['mime']})")
        if att["type"] == "text":
            lines.append(f"Content preview:\n{att['content'][:2000]}\n---")
        elif att["type"] == "image":
            lines.append("(image attachment — will be sent as image to vision-capable models)")
        else:
            lines.append(f"(could not parse: {att.get('content','')})")
    return "\n".join(lines)


def _parse_llm_response(raw: str) -> dict:
    """Extract JSON from LLM response, repair if needed."""
    try:
        raw = raw.strip()
        # Strip markdown code blocks if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json
            return json.loads(repair_json(raw))
        except Exception:
            logger.error(f"Could not parse LLM response: {raw[:500]}")
            return {"answers": [], "evidence_matches": [], "follow_up_keys": [], "notes": "parse error"}


# ──────────────────────────────────────────────────────────────
# Main extraction entry point
# ──────────────────────────────────────────────────────────────

async def extract_from_email(
    cfg: dict,
    questions: list,
    evidence_tasks: list,
    body_text: str,
    parsed_attachments: list,
    settings,
    system_prompt: str | None = None,
    extraction_prompt_template: str | None = None,
) -> dict:
    """
    Run LLM extraction.
    cfg: automation_config row from DB
    Returns raw parsed dict from LLM.
    """
    provider = cfg.get("extraction_provider") or "gemini"
    model = cfg.get("extraction_model")

    # Resolve model default per provider
    if not model:
        if provider == "anthropic":
            model = settings.ANTHROPIC_MODEL
        elif provider == "groq":
            model = settings.GROQ_MODEL
        else:
            model = settings.GEMINI_MODEL

    # Only pass attachments to the LLM when there are evidence tasks to match against.
    # If no evidence is requested, attachments are irrelevant — skip them entirely.
    active_attachments = parsed_attachments if evidence_tasks else []

    image_attachments = [a for a in active_attachments if a["type"] == "image"]

    # Use DB-loaded prompts when provided, otherwise fall back to hardcoded defaults
    active_system_prompt = system_prompt or SYSTEM_PROMPT
    active_extraction_template = extraction_prompt_template or EXTRACTION_PROMPT

    prompt = active_extraction_template.format(
        questions_block=_build_questions_block(questions),
        evidence_block=_build_evidence_block(evidence_tasks),
        body_text=(body_text or "")[:8000],
        attachments_block=_build_attachments_block(active_attachments),
    )

    logger.info(f"Email extraction: provider={provider}, model={model}, "
                f"questions={len(questions)}, evidence={len(evidence_tasks)}, "
                f"attachments={len(parsed_attachments)}")

    # API key resolved from central llm_providers table by get_automation_config()
    api_key = cfg.get("_api_key") or ""

    try:
        from .llm_caller import call_llm
        raw, tok_in, tok_out, dur_ms = await call_llm(
            provider=provider, model=model, api_key=api_key,
            system_prompt=active_system_prompt, user_prompt=prompt,
            temperature=0.1, max_tokens=2048, settings=settings,
            image_attachments=image_attachments,
        )

        result = _parse_llm_response(raw)
        logger.info(f"Extracted: {len(result.get('answers',[]))} answers, "
                    f"{len(result.get('evidence_matches',[]))} evidence matches")
        return result, provider, model, tok_in, tok_out, dur_ms

    except Exception as e:
        logger.error(f"LLM extraction failed ({provider}/{model}): {e}")
        return {"answers": [], "evidence_matches": [], "follow_up_keys": [], "notes": str(e)}, provider, model, 0, 0, 0
