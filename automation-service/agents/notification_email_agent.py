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
    "iso360_activated": {
        "subject": "ISO360 Compliance Service Activated",
        "greeting": "Hello,",
        "intro": "Your ISO360 compliance service has been activated for your ISO certification plan.",
        "what_it_means": "ISO360 provides year-round compliance management with recurring activity schedules, reminders, and evidence tracking.",
        "what_to_expect": "You will shortly receive a short onboarding questionnaire. Your answers help us personalise the activity schedule to your organisation.",
        "closing": "Best regards,\nThe DNA Team",
    },
    "iso360_deactivated": {
        "subject": "ISO360 Compliance Service Deactivated",
        "greeting": "Hello,",
        "intro": "Your ISO360 compliance service has been deactivated for your ISO certification plan.",
        "what_it_means": "Recurring activity schedules and automated reminders will no longer be generated.",
        "what_is_preserved": "All your existing compliance data and evidence are preserved. ISO360 can be re-activated at any time.",
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
        return _get_fallback(notification_type, variables)

    system_prompt = system_row["prompt_text"]
    user_template = user_row["prompt_text"]
    model         = system_row.get("model") or "gemini-2.5-flash"
    temperature   = float(system_row.get("temperature") or 0.4)

    # Fill {{variables}} in user prompt
    user_prompt = user_template
    for key, val in variables.items():
        user_prompt = user_prompt.replace(f"{{{{{key}}}}}", str(val) if val is not None else "")

    try:
        from db_client import get_ai_config_for_service
        ai_cfg   = await get_ai_config_for_service("notification")
        provider = ai_cfg["provider"]
        api_key  = ai_cfg["_api_key"]
        from .llm_caller import call_llm
        result_text, _, _, _ = await call_llm(
            provider=provider, model=model, api_key=api_key,
            system_prompt=system_prompt, user_prompt=user_prompt,
            temperature=temperature, max_tokens=2048, settings=settings,
        )
        sections = _parse_json_response(result_text)
        if not sections or "subject" not in sections:
            raise ValueError("LLM response missing required 'subject' key")
        return sections
    except Exception as e:
        logger.warning(f"Notification agent LLM call failed ({notification_type}): {e}")
        return _get_fallback(notification_type, variables)


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


_FALLBACK_HE: dict[str, dict] = {
    "welcome_customer": {
        "subject": "ברוכים הבאים לפלטפורמת DNA Compliance",
        "greeting": "ברוכים הבאים,",
        "intro": "חשבונך נוצר בהצלחה בפלטפורמת הציות של DNA.",
        "portal_section": "תוכל לגשת לפורטל שלך באמצעות הקישור שיסופק על ידי היועץ שלך.",
        "next_steps": "היועץ שלך ייצור איתך קשר בקרוב להגדרת תוכנית הסמכת ISO.",
        "closing": "בברכה,\nצוות DNA",
    },
    "welcome_plan": {
        "subject": "מסע הסמכת ה-ISO שלך החל",
        "greeting": "שלום,",
        "iso_overview": "נרשמת לתוכנית הסמכת ISO.",
        "journey_overview": "הצוות שלנו ילווה אותך בתהליך ההסמכה שלב אחר שלב.",
        "email_channel": "תוכל להשיב לכל אימייל שנשלח אליך עם תשובותיך. הבינה המלאכותית שלנו תעבד אותן אוטומטית.",
        "portal_intro": "גש לפורטל הציות שלך באמצעות הקישור למטה כדי לעקוב אחר ההתקדמות ולהעלות מסמכים.",
        "what_to_expect": "תקבל את השאלון הראשון שלך בקרוב.",
        "closing": "בברכה,\nצוות DNA",
    },
    "iso360_reminder": {
        "subject": "סקירת ציות ISO שנתית",
        "greeting": "שלום,",
        "reminder_intro": "הגיע הזמן לסקירת ציות ה-ISO השנתית שלך.",
        "evidence_summary": "אנא סקור את פריטי הראיות בפורטל שלך.",
        "action_guidance": "התחבר לפורטל שלך כדי לראות מה צריך לחדש ולהעלות את המסמכים הנדרשים.",
        "portal_cta": "פתח את פורטל הציות שלך כדי להתחיל.",
        "closing": "בברכה,\nצוות DNA",
    },
    "announcement": {
        "subject": "עדכון חשוב מ-DNA",
        "greeting": "שלום,",
        "body": "יש לנו עדכון חשוב לשתף איתך.",
        "closing": "בברכה,\nצוות DNA",
    },
    "iso360_activated": {
        "subject": "שירות ISO360 הופעל",
        "greeting": "שלום,",
        "intro": "שירות הציות ISO360 שלך הופעל עבור תוכנית הסמכת ה-ISO שלך.",
        "what_it_means": "ISO360 מספק ניהול ציות לאורך כל השנה עם לוחות זמנים לפעילויות חוזרות, תזכורות ומעקב ראיות.",
        "what_to_expect": "בקרוב תקבל שאלון קצר. תשובותיך יעזרו לנו להתאים את לוח הפעילויות לארגון שלך.",
        "closing": "בברכה,\nצוות DNA",
    },
    "iso360_deactivated": {
        "subject": "שירות ISO360 הושבת",
        "greeting": "שלום,",
        "intro": "שירות הציות ISO360 שלך הושבת עבור תוכנית הסמכת ה-ISO שלך.",
        "what_it_means": "לוחות זמנים לפעילויות חוזרות ותזכורות אוטומטיות לא יופקו עוד.",
        "what_is_preserved": "כל נתוני הציות והראיות הקיימים שלך נשמרים. ניתן להפעיל מחדש את ISO360 בכל עת.",
        "closing": "אם יש לך שאלות, אנא צור קשר עם יועץ הציות שלך.\n\nבברכה,\nצוות DNA",
    },
}


def _get_fallback(notification_type: str, variables: dict) -> dict:
    is_hebrew = variables.get("language", "").lower() == "hebrew"
    bank = _FALLBACK_HE if is_hebrew else _FALLBACK
    return bank.get(notification_type) or {
        "subject": "עדכון מ-DNA" if is_hebrew else "A message from DNA",
        "greeting": "שלום," if is_hebrew else "Hello,",
        "body": "התחבר לפורטל הציות שלך לעדכונים." if is_hebrew else "Please log in to your compliance portal for updates.",
        "closing": "בברכה,\nצוות DNA" if is_hebrew else "Best regards,\nThe DNA Team",
    }
