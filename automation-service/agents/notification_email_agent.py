"""
Notification Email Agent
========================
Generates outbound notification email content using LLM prompts
stored in ai_prompts table. Used for: welcome_customer, welcome_plan,
iso360_reminder, announcement.

Returns a dict of sections (plain text) that the caller renders into HTML.
Falls back to a minimal static message if LLM fails.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_FALLBACK: dict[str, dict] = {
    "welcome_customer": {
        "subject": "Welcome to DNA Compliance Platform",
        "greeting": "Welcome,",
        "intro": "Your account has been created on the DNA compliance platform.",
        "portal_section": "You can access your portal using the link provided by your consultant.",
        "next_steps": "Your consultant will be in touch shortly to set up your ISO certification plan.",
        "closing": "Best regards,\nThe DNA Team",
    },
    "welcome_plan": {
        "subject": "Your ISO Certification Journey Has Started",
        "greeting": "Hello,",
        "iso_overview": "You have been enrolled in an ISO certification plan.",
        "journey_overview": "Our team will guide you through the certification process step by step.",
        "email_channel": "You can reply to any email we send with your answers. Our AI will process them automatically.",
        "portal_intro": "Access your compliance portal using the link below to track progress and upload documents.",
        "what_to_expect": "You will receive your first questionnaire email shortly.",
        "closing": "Best regards,\nThe DNA Team",
    },
    "iso360_reminder": {
        "subject": "Annual ISO Compliance Review",
        "greeting": "Hello,",
        "reminder_intro": "It is time for your annual ISO compliance review.",
        "evidence_summary": "Please review the evidence items listed in your portal.",
        "action_guidance": "Log in to your portal to see what needs to be renewed and upload the required documents.",
        "portal_cta": "Open your compliance portal to get started.",
        "closing": "Best regards,\nThe DNA Team",
    },
    "announcement": {
        "subject": "Important Update from DNA",
        "greeting": "Hello,",
        "body": "We have an important update to share with you.",
        "closing": "Best regards,\nThe DNA Team",
    },
    "iso360_paused": {
        "subject": "ISO360 Service Paused",
        "greeting": "Hello,",
        "intro": "Your ISO360 premium compliance service has been temporarily paused by your account administrator.",
        "what_it_means": "No new annual review tasks or reminders will be generated during the pause period.",
        "what_is_preserved": "All your existing progress, collected evidence, and compliance data are fully preserved. The service can be re-activated at any time.",
        "closing": "If you have any questions, please contact your compliance consultant.\n\nBest regards,\nThe DNA Team",
    },
}


async def generate_notification_email(
    notification_type: str,   # 'welcome_customer' | 'welcome_plan' | 'iso360_reminder' | 'announcement'
    variables: dict,           # filled into {{placeholder}} in user prompt
    cfg: dict,                 # automation config (holds LLM provider/model/key via _api_key)
    settings,
    ai_prompt_getter,          # async callable: get_ai_prompt(key) -> dict|None
) -> dict:
    """
    Returns a dict of plain-text email sections.
    Falls back to static template on any LLM failure.
    """
    system_key = f"{notification_type}_system"
    user_key   = f"{notification_type}_user"

    system_row = await ai_prompt_getter(system_key)
    user_row   = await ai_prompt_getter(user_key)

    if not system_row or not user_row:
        logger.warning(f"Notification agent: prompts not found for '{notification_type}', using fallback")
        return _FALLBACK.get(notification_type, _get_generic_fallback(notification_type))

    system_prompt = system_row["prompt_text"]
    user_template = user_row["prompt_text"]
    model         = system_row.get("model") or "gemini-2.5-flash"
    temperature   = float(system_row.get("temperature") or 0.4)

    # Fill {{variables}} in user prompt
    user_prompt = user_template
    for key, val in variables.items():
        user_prompt = user_prompt.replace(f"{{{{{key}}}}}", str(val) if val is not None else "")

    try:
        result_text = await _call_llm(system_prompt, user_prompt, model, temperature, cfg, settings)
        sections = _parse_json_response(result_text)
        if not sections or "subject" not in sections:
            raise ValueError("LLM response missing required 'subject' key")
        return sections
    except Exception as e:
        logger.warning(f"Notification agent LLM call failed ({notification_type}): {e}")
        return _FALLBACK.get(notification_type, _get_generic_fallback(notification_type))


async def _call_llm(system_prompt: str, user_prompt: str, model: str, temperature: float, cfg: dict, settings) -> str:
    provider = (cfg.get("llm_provider") or "gemini").lower()
    api_key  = cfg.get("_api_key") or ""

    if provider == "gemini":
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=api_key or getattr(settings, "GOOGLE_API_KEY", ""))
        resp = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=2048,
            ),
        )
        return resp.text

    elif provider == "claude":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key or getattr(settings, "ANTHROPIC_API_KEY", ""))
        msg = await client.messages.create(
            model=model, max_tokens=2048, temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text

    elif provider == "groq":
        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key or getattr(settings, "GROQ_API_KEY", ""))
        resp = await client.chat.completions.create(
            model=model, temperature=temperature, max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    else:  # openai
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key or getattr(settings, "OPENAI_API_KEY", ""))
        resp = await client.chat.completions.create(
            model=model, temperature=temperature, max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _get_generic_fallback(notification_type: str) -> dict:
    return {
        "subject": "A message from DNA",
        "greeting": "Hello,",
        "body": "Please log in to your compliance portal for updates.",
        "closing": "Best regards,\nThe DNA Team",
    }
