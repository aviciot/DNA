"""
Extraction Reply Agent
======================
Drafts a professional follow-up email to send to the customer after extraction.
Returns structured content (4 sections) which the caller formats as plain text.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

REPLY_SYSTEM_PROMPT = """You are a professional compliance assistant writing a brief follow-up email to a customer.
Be concise, warm, and professional. Write in the customer's language (en=English, he=Hebrew).
Return ONLY valid JSON — no markdown, no text outside the JSON object.
JSON keys: applied_summary, clarification_requests, unmatched_note, closing"""

REPLY_PROMPT_TEMPLATE = """Language: {language}

Applied answers ({applied_count}):
{applied_lines}

Items needing clarification ({review_count}):
{review_lines}

Keys where customer asked a question instead of answering ({unmatched_count}):
{unmatched_lines}

Write 1-2 sentences per section. For applied_summary acknowledge what was received.
For clarification_requests ask gently for clearer answers on those items.
For unmatched_note if any — note that we will follow up with more details.
For closing — friendly professional sign-off.
If a section has no items, return an empty string "" for that key.
Return ONLY the JSON object."""


def _parse_reply_response(raw: str) -> dict:
    try:
        raw = raw.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json
            return json.loads(repair_json(raw))
        except Exception:
            logger.warning(f"Could not parse reply agent response: {raw[:300]}")
            return {}


async def draft_reply_email(
    cfg: dict,
    applied: list,          # [{placeholder_key, value, reasoning}]
    needs_review: list,     # [{placeholder_key, value, reasoning}]
    unmatched: list,        # [placeholder_key strings]
    language: str,
    settings,
) -> dict:
    """
    Use the configured LLM to draft reply email content.
    Returns dict with keys: applied_summary, clarification_requests, unmatched_note, closing.
    Falls back to generic text if LLM fails.
    """
    def _fmt_applied(items: list) -> str:
        if not items:
            return "(none)"
        return "\n".join(f"- {a.get('placeholder_key','')}: {str(a.get('value',''))[:80]}"
                         for a in items)

    def _fmt_review(items: list) -> str:
        if not items:
            return "(none)"
        return "\n".join(f"- {a.get('placeholder_key','')}: {str(a.get('value',''))[:80]} "
                         f"(confidence {a.get('confidence',0):.0%})"
                         for a in items)

    prompt = REPLY_PROMPT_TEMPLATE.format(
        language="Hebrew" if language == "he" else "English",
        applied_count=len(applied),
        applied_lines=_fmt_applied(applied),
        review_count=len(needs_review),
        review_lines=_fmt_review(needs_review),
        unmatched_count=len(unmatched),
        unmatched_lines="\n".join(f"- {k}" for k in unmatched) if unmatched else "(none)",
    )

    provider = cfg.get("extraction_provider") or "gemini"
    model = cfg.get("extraction_model")
    if not model:
        if provider == "anthropic":
            model = settings.ANTHROPIC_MODEL
        elif provider == "groq":
            model = settings.GROQ_MODEL
        else:
            model = settings.GEMINI_MODEL

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await client.messages.create(
                model=model,
                max_tokens=512,
                system=REPLY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text
        elif provider == "groq":
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=512,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content
        else:
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            m = genai.GenerativeModel(model, system_instruction=REPLY_SYSTEM_PROMPT)
            resp = await m.generate_content_async(prompt)
            raw = resp.text

        content = _parse_reply_response(raw)
        if content.get("applied_summary") or content.get("closing"):
            return content
    except Exception as e:
        logger.warning(f"Reply agent LLM call failed ({provider}/{model}): {e}")

    # Fallback: generic text
    if language == "he":
        return {
            "applied_summary": f"קיבלנו את תשובותיכם — {len(applied)} פריט/ים עודכנו במערכת." if applied else "",
            "clarification_requests": f"ישנם {len(needs_review)} פריט/ים הדורשים בירור נוסף." if needs_review else "",
            "unmatched_note": "נשלח לכם שאלון נוסף בקרוב עם שאלות שעדיין ממתינות." if unmatched else "",
            "closing": "תודה על שיתוף הפעולה.",
        }
    else:
        return {
            "applied_summary": f"Thank you — {len(applied)} item(s) have been recorded." if applied else "",
            "clarification_requests": f"We have {len(needs_review)} item(s) that need a bit more detail." if needs_review else "",
            "unmatched_note": "We will follow up shortly with any remaining open questions." if unmatched else "",
            "closing": "Thank you for your cooperation.",
        }
