"""
Email Sender
============
Supports Gmail SMTP and SendGrid.
HTML template is built inline — branded, clean, compliance-ready.
"""
import logging
import secrets
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Localisation strings
# ──────────────────────────────────────────────────────────────
_L = {
    "en": {
        "action_required": "Action Required",
        "follow_up": "Follow-up",
        "hi": "Hi",
        "intro": "As part of your <strong>{iso_code}</strong> compliance process, we need your input on <strong>{n} item{s}</strong>. Please reply to this email with your answers, or upload documents as attachments.",
        "questions_heading": "Questions",
        "evidence_heading": "Documents / Evidence",
        "reply_tip_title": "💬 How to reply:",
        "reply_tip": "Simply reply to this email. Write your answers in plain text — our AI will automatically match them to the right fields. For document uploads, attach the files directly to your reply.",
        "open_portal": "🔗 Open Compliance Portal",
        "or_reply": "Or simply reply to this email with your answers",
        "case_ref": "Case reference",
        "followup_note": "📩 Follow-up #{n} — We sent a similar request a few days ago and still have {total} item{s} awaiting your response. If you have already replied, please disregard this message.",
        "do_not_unsub": "This email was sent automatically. Do not unsubscribe — it contains required compliance information.",
        "dir": "ltr",
        "lang": "en",
        "align": "left",
    },
    "he": {
        "action_required": "נדרשת פעולה",
        "follow_up": "תזכורת",
        "hi": "שלום",
        "intro": "כחלק מתהליך עמידתכם בתקן <strong>{iso_code}</strong>, אנו זקוקים לתגובתכם על <strong>{n} פריט{s_he}</strong>. אנא השיבו למייל זה עם תשובותיכם, או העלו מסמכים כקבצים מצורפים.",
        "questions_heading": "שאלות",
        "evidence_heading": "מסמכים / ראיות",
        "reply_tip_title": "💬 כיצד להשיב:",
        "reply_tip": "פשוט השיבו למייל זה. כתבו את תשובותיכם בטקסט רגיל — הבינה המלאכותית שלנו תתאים אותן אוטומטית לשדות המתאימים. להעלאת מסמכים, צרפו את הקבצים ישירות לתשובתכם.",
        "open_portal": "🔗 פתח פורטל ציות",
        "or_reply": "או השיבו למייל זה עם תשובותיכם",
        "case_ref": "מספר הפנייה",
        "followup_note": "📩 תזכורת #{n} — שלחנו בקשה דומה לפני מספר ימים ועדיין ממתינים ל-{total} פריט{s_he}. אם כבר השבתם, אנא התעלמו מהודעה זו.",
        "do_not_unsub": "מייל זה נשלח אוטומטית. הוא מכיל מידע ציות נדרש.",
        "dir": "rtl",
        "lang": "he",
        "align": "right",
    },
}


# ──────────────────────────────────────────────────────────────
# HTML email template
# ──────────────────────────────────────────────────────────────
def build_email_html(
    customer_name: str,
    iso_code: str,
    iso_name: str,
    questions: list,        # [{placeholder_key, question, hint, example_value}]
    evidence_tasks: list,   # [{task_id, title, description}]
    case_ref: str,
    portal_url: Optional[str] = None,
    is_followup: bool = False,
    followup_number: int = 1,
    language: str = "en",
) -> tuple[str, str]:
    """Returns (subject, html_body)."""
    lc = _L.get(language) or _L["en"]
    q_count = len(questions)
    e_count = len(evidence_tasks)
    total = q_count + e_count
    s = "s" if total != 1 else ""
    s_he = "ים" if total != 1 else ""

    action_label = lc["follow_up"] if is_followup else lc["action_required"]
    followup_note = (
        f'<div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:12px 16px;margin-bottom:20px;border-radius:4px">'
        + lc["followup_note"].format(n=followup_number, total=total, s=s, s_he=s_he)
        + "</div>"
    ) if is_followup else ""

    subject_prefix = f"[DNA-{case_ref}] "
    if is_followup:
        subject = f"{subject_prefix}{lc['follow_up']}: {iso_code} — {total} {lc['action_required'].lower()}"
    else:
        subject = f"{subject_prefix}{iso_code} — {total} item{s} need your attention"

    questions_html = ""
    if questions:
        items_html = ""
        for i, q in enumerate(questions, 1):
            hint = f'<div style="font-size:12px;color:#6b7280;margin-top:4px">{q.get("hint","")}</div>' if q.get("hint") else ""
            example = f'<div style="font-size:11px;color:#9ca3af;font-style:italic;margin-top:2px">Example: {q.get("example_value","")}</div>' if q.get("example_value") else ""
            items_html += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6;vertical-align:top">
                <div style="display:inline-block;background:#dbeafe;color:#1e40af;font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;margin-bottom:6px">Q{i}</div>
                <div style="font-weight:600;color:#111827">{q.get('question', q.get('placeholder_key',''))}</div>
                {hint}{example}
              </td>
            </tr>"""
        questions_html = f"""
        <div style="margin-bottom:24px">
          <h3 style="font-size:14px;font-weight:700;color:#374151;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid #e5e7eb">
            📋 {lc['questions_heading']} ({q_count})
          </h3>
          <table width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
            {items_html}
          </table>
        </div>"""

    evidence_html = ""
    if evidence_tasks:
        items_html = ""
        for i, ev in enumerate(evidence_tasks, 1):
            desc = f'<div style="font-size:12px;color:#6b7280;margin-top:4px">{ev.get("description","")}</div>' if ev.get("description") else ""
            items_html += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #fef3c7;vertical-align:top">
                <div style="display:inline-block;background:#fef3c7;color:#92400e;font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;margin-bottom:6px">FILE {i}</div>
                <div style="font-weight:600;color:#111827">{ev.get('title','')}</div>
                {desc}
              </td>
            </tr>"""
        evidence_html = f"""
        <div style="margin-bottom:24px">
          <h3 style="font-size:14px;font-weight:700;color:#374151;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid #fde68a">
            📎 {lc['evidence_heading']} ({e_count})
          </h3>
          <table width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #fde68a;border-radius:8px;overflow:hidden;background:#fffbeb">
            {items_html}
          </table>
        </div>"""

    portal_section = ""
    if portal_url:
        portal_section = f"""
        <div style="text-align:center;margin:28px 0">
          <a href="{portal_url}" style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px">
            {lc['open_portal']}
          </a>
          <div style="font-size:11px;color:#9ca3af;margin-top:8px">{lc['or_reply']}</div>
        </div>"""

    intro_html = lc["intro"].format(iso_code=iso_code, n=total, s=s, s_he=s_he)

    html = f"""<!DOCTYPE html>
<html lang="{lc['lang']}" dir="{lc['dir']}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellspacing="0" cellpadding="0" bgcolor="#f9fafb">
<tr><td align="center" style="padding:32px 16px">
<table width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1e40af,#7c3aed);border-radius:12px 12px 0 0;padding:28px 32px">
    <div style="color:#fff;font-size:22px;font-weight:700">DNA Compliance</div>
    <div style="color:#bfdbfe;font-size:13px;margin-top:4px">{action_label} · {iso_code} — {iso_name}</div>
  </td></tr>

  <!-- Body -->
  <tr><td style="background:#fff;padding:32px;border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;text-align:{lc['align']}">
    {followup_note}
    <p style="font-size:15px;color:#374151;margin:0 0 16px">{lc['hi']} <strong>{customer_name}</strong>,</p>
    <p style="font-size:14px;color:#6b7280;margin:0 0 24px;line-height:1.6">
      {intro_html}
    </p>

    {questions_html}
    {evidence_html}
    {portal_section}

    <div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:14px 16px;border-radius:4px;font-size:13px;color:#166534;margin-top:8px">
      <strong>{lc['reply_tip_title']}</strong> {lc['reply_tip']}
    </div>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#f9fafb;border:1px solid #e5e7eb;border-top:0;border-radius:0 0 12px 12px;padding:16px 32px">
    <div style="font-size:11px;color:#9ca3af;text-align:center">
      {lc['case_ref']}: <strong style="color:#6b7280">{case_ref}</strong> ·
      {iso_code} ·
      {lc['do_not_unsub']}
    </div>
    <div style="font-size:10px;color:#cbd5e1;text-align:center;margin-top:8px;padding-top:8px;border-top:1px solid #f1f5f9">
      💬 Starting a new email thread? Include <strong style="color:#94a3b8">DNA-{case_ref}</strong> anywhere in your message and we will automatically link it to this request.
    </div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return subject, html


def build_text_fallback(customer_name: str, questions: list, evidence_tasks: list, case_ref: str, language: str = "en") -> str:
    lc = _L.get(language) or _L["en"]
    lines = [f"{lc['hi']} {customer_name},", ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"Q{i}: {q.get('question', q.get('placeholder_key',''))}")
        if q.get("hint"):
            lines.append(f"    Hint: {q['hint']}")
        lines.append("")
    if evidence_tasks:
        lines.append(lc["evidence_heading"] + ":")
        for ev in evidence_tasks:
            lines.append(f"  - {ev.get('title','')}: {ev.get('description','')}")
        lines.append("")
    lines.append(f"{lc['case_ref']}: DNA-{case_ref}")
    lines.append(f"(Starting a new email thread? Include DNA-{case_ref} in your message to link it to this request.)")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Senders
# ──────────────────────────────────────────────────────────────
async def send_via_gmail_smtp(
    gmail_address: str,
    gmail_app_password: str,
    to_addresses: list[str],
    reply_to: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = gmail_address
        msg["To"] = ", ".join(to_addresses)
        msg["Subject"] = subject
        msg["Reply-To"] = reply_to
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, to_addresses, msg.as_string())
        logger.info(f"Gmail SMTP sent to {to_addresses}")
        return True
    except Exception as e:
        logger.error(f"Gmail SMTP failed: {e}")
        return False


async def send_via_sendgrid(
    api_key: str,
    from_email: str,
    from_name: str,
    to_addresses: list[str],
    reply_to: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    try:
        import sendgrid as sg_module
        from sendgrid.helpers.mail import Mail, Email, To, Content, ReplyTo
        sg = sg_module.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=Email(from_email, from_name),
            to_emails=[To(addr) for addr in to_addresses],
            subject=subject,
        )
        message.reply_to = ReplyTo(reply_to)
        message.add_content(Content("text/plain", text_body))
        message.add_content(Content("text/html", html_body))
        response = sg.send(message)
        logger.info(f"SendGrid sent to {to_addresses}, status={response.status_code}")
        return response.status_code in (200, 202)
    except Exception as e:
        body = getattr(e, 'body', b'')
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='replace')
        logger.error(f"SendGrid failed [{type(e).__name__}]: {e} | detail: {body}")
        return False


async def send_campaign_email(
    cfg: dict,
    customer_name: str,
    iso_code: str,
    iso_name: str,
    to_addresses: list[str],
    token: str,
    questions: list,
    evidence_tasks: list,
    portal_url: Optional[str] = None,
    is_followup: bool = False,
    followup_number: int = 1,
    language: str = "en",
) -> tuple[bool, str]:
    """High-level sender. Returns (success, subject)."""
    case_ref = token[:8].upper()
    gmail_address = cfg.get("gmail_address", "")
    reply_to = f"{gmail_address.split('@')[0]}+collect_{token}@{gmail_address.split('@')[1]}" if gmail_address else gmail_address

    subject, html = build_email_html(
        customer_name=customer_name,
        iso_code=iso_code,
        iso_name=iso_name,
        questions=questions,
        evidence_tasks=evidence_tasks,
        case_ref=case_ref,
        portal_url=portal_url,
        is_followup=is_followup,
        followup_number=followup_number,
        language=language,
    )
    text = build_text_fallback(customer_name, questions, evidence_tasks, case_ref, language=language)

    provider = cfg.get("email_provider", "gmail")

    if provider == "sendgrid" and cfg.get("sendgrid_api_key"):
        ok = await send_via_sendgrid(
            api_key=cfg["sendgrid_api_key"],
            from_email=cfg.get("sendgrid_from_email", gmail_address),
            from_name=cfg.get("sendgrid_from_name", "DNA Compliance"),
            to_addresses=to_addresses,
            reply_to=reply_to,
            subject=subject,
            html_body=html,
            text_body=text,
        )
    else:
        ok = await send_via_gmail_smtp(
            gmail_address=gmail_address,
            gmail_app_password=cfg.get("gmail_app_password", ""),
            to_addresses=to_addresses,
            reply_to=reply_to,
            subject=subject,
            html_body=html,
            text_body=text,
        )

    return ok, subject


async def send_extraction_reply_email(
    cfg: dict,
    to_emails: list[str],
    customer_name: str,
    language: str,
    llm_content: dict,
    applied_count: int,
    review_count: int,
    subject_ref: str,
) -> bool:
    """
    Send a plain-text acknowledgement email after extraction.
    Uses the same SMTP/SendGrid infrastructure as campaign emails.
    """
    if not to_emails:
        logger.warning("send_extraction_reply_email: no recipients, skipping")
        return False

    # Build subject
    if subject_ref:
        subject = f"Re: {subject_ref}"
    else:
        subject = "Thank you for your compliance response"

    # Build body from LLM sections
    greeting = "שלום" if language == "he" else "Hi"
    lines = [f"{greeting} {customer_name},", ""]

    applied_summary = (llm_content.get("applied_summary") or "").strip()
    evidence_summary = (llm_content.get("evidence_summary") or "").strip()
    clarification = (llm_content.get("clarification_requests") or "").strip()
    unmatched_note = (llm_content.get("unmatched_note") or "").strip()
    closing = (llm_content.get("closing") or "").strip()

    if applied_summary:
        lines.append(applied_summary)
        lines.append("")
    if evidence_summary:
        lines.append(evidence_summary)
        lines.append("")
    if clarification:
        lines.append(clarification)
        lines.append("")
    if unmatched_note:
        lines.append(unmatched_note)
        lines.append("")
    if closing:
        lines.append(closing)
        lines.append("")

    lines.append("DNA Compliance Team")
    body = "\n".join(lines)

    gmail_address = cfg.get("gmail_address", "")
    provider = cfg.get("email_provider", "gmail")

    if provider == "sendgrid" and cfg.get("sendgrid_api_key"):
        ok = await send_via_sendgrid(
            api_key=cfg["sendgrid_api_key"],
            from_email=cfg.get("sendgrid_from_email", gmail_address),
            from_name=cfg.get("sendgrid_from_name", "DNA Compliance"),
            to_addresses=to_emails,
            reply_to=gmail_address,
            subject=subject,
            html_body=f"<pre style='font-family:sans-serif'>{body}</pre>",
            text_body=body,
        )
    else:
        ok = await send_via_gmail_smtp(
            gmail_address=gmail_address,
            gmail_app_password=cfg.get("gmail_app_password", ""),
            to_addresses=to_emails,
            reply_to=gmail_address,
            subject=subject,
            html_body=f"<pre style='font-family:sans-serif'>{body}</pre>",
            text_body=body,
        )

    if ok:
        logger.info(f"Extraction reply sent to {to_emails} (subject: {subject})")
    else:
        logger.warning(f"Extraction reply delivery failed to {to_emails}")
    return ok


def _build_notification_html(sections: dict, portal_url: str = "", iso_code: str = "", iso_name: str = "") -> str:
    """Render LLM-generated sections into a branded HTML email with optional portal CTA button."""

    # Section keys that get visual treatment (bold label above text)
    _LABELLED = {
        "iso_overview":     "About Your ISO Standard",
        "journey_overview": "Your Certification Journey",
        "email_channel":    "How Evidence Collection Works",
        "portal_intro":     "Your Compliance Portal",
        "what_to_expect":   "What Happens Next",
        "next_steps":       "Next Steps",
    }
    # Keys rendered as plain paragraphs only
    _PLAIN = {"greeting", "intro", "portal_section", "closing"}
    _SKIP = {"subject"}

    greeting = sections.get("greeting", "Hello,")

    # ISO badge for plan welcome emails
    iso_badge = ""
    if iso_code:
        iso_badge = f"""
        <div style="display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;
                    border-radius:8px;padding:10px 18px;margin:12px 0 24px">
          <span style="font-size:13px;font-weight:700;color:#1d4ed8">{iso_code}</span>
          {"<span style='font-size:12px;color:#3b82f6;margin-left:8px'>" + iso_name + "</span>" if iso_name else ""}
        </div>"""

    parts = []
    parts.append(f"<p style='font-size:17px;font-weight:600;color:#0f172a;margin:0 0 4px'>{greeting}</p>")
    if iso_badge:
        parts.append(iso_badge)

    # intro always first plain paragraph
    intro = sections.get("intro", "")
    if intro:
        parts.append(f"<p style='color:#374151;line-height:1.75;margin:16px 0'>{intro}</p>")

    # Labelled sections (skip portal_section — handled by button below)
    for key, label in _LABELLED.items():
        val = sections.get(key, "")
        if not val:
            continue
        # Strip any raw URLs from portal_intro — we'll render a button instead
        if key == "portal_intro" and portal_url:
            import re as _re
            val = _re.sub(r'https?://\S+', '', val).strip()
            if not val:
                continue
        parts.append(f"""
        <div style="margin:20px 0;padding:16px 20px;background:#f8fafc;
                    border-left:4px solid #2563eb;border-radius:0 8px 8px 0">
          <p style="margin:0 0 6px;font-size:11px;font-weight:700;
                    text-transform:uppercase;letter-spacing:.8px;color:#6366f1">{label}</p>
          <p style="margin:0;color:#374151;line-height:1.75">{val}</p>
        </div>""")

    # Plain sections (closing, portal_section, etc.)
    for key in ("portal_section", "closing"):
        val = sections.get(key, "")
        if not val:
            continue
        if key == "portal_section" and portal_url:
            import re as _re
            val = _re.sub(r'https?://\S+', '', val).strip()
            if not val:
                continue
        parts.append(f"<p style='color:#374151;line-height:1.75;margin:16px 0'>{val}</p>")

    # Remaining plain sections
    handled = set(_LABELLED) | _PLAIN | _SKIP | {"intro"}
    for key, val in sections.items():
        if key in handled or not val:
            continue
        parts.append(f"<p style='color:#374151;line-height:1.75;margin:16px 0'>{val}</p>")

    # Portal CTA button (always rendered when portal_url is set, regardless of LLM text)
    portal_btn = ""
    if portal_url:
        portal_btn = f"""
      <div style="text-align:center;margin:32px 0 8px">
        <a href="{portal_url}"
           style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                  padding:14px 36px;border-radius:10px;font-weight:700;font-size:15px;
                  letter-spacing:-.2px;box-shadow:0 2px 8px rgba(37,99,235,.3)">
          🔗 Open Your Compliance Portal
        </a>
        <p style="margin:10px 0 0;font-size:12px;color:#94a3b8">
          Or copy this link: <a href="{portal_url}" style="color:#2563eb;word-break:break-all">{portal_url}</a>
        </p>
      </div>"""

    inner = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Inter',Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr><td align="center" style="padding:40px 16px">
    <table width="600" cellpadding="0" cellspacing="0" role="presentation"
           style="background:#ffffff;border-radius:14px;overflow:hidden;
                  box-shadow:0 4px 16px rgba(0,0,0,.10);max-width:600px;width:100%">

      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#1d4ed8 0%,#2563eb 60%,#3b82f6 100%);padding:28px 36px">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td>
              <span style="color:#ffffff;font-size:24px;font-weight:800;letter-spacing:-1px">DNA</span>
              <span style="color:#bfdbfe;font-size:13px;margin-left:10px;font-weight:500">Compliance Platform</span>
            </td>
            <td align="right">
              <span style="background:rgba(255,255,255,.15);color:#e0f2fe;font-size:11px;
                           font-weight:600;padding:4px 10px;border-radius:20px">
                Compliance Team
              </span>
            </td>
          </tr>
        </table>
      </td></tr>

      <!-- Body -->
      <tr><td style="padding:36px 36px 20px">
        {inner}
        {portal_btn}
      </td></tr>

      <!-- Footer -->
      <tr><td style="background:#f8fafc;padding:20px 36px;border-top:1px solid #e2e8f0">
        <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.6">
          This message was sent automatically by DNA Compliance Platform.
          If you have questions, reply to this email and our compliance team will assist you.
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>"""


async def send_notification_email(
    cfg: dict,
    to_address: str,
    subject: str,
    sections: dict,
    language: str = "en",
    portal_url: str = "",
    iso_code: str = "",
    iso_name: str = "",
) -> bool:
    """Send a notification email (welcome, announcement, reminder) to a single recipient."""
    html = _build_notification_html(sections, portal_url=portal_url, iso_code=iso_code, iso_name=iso_name)
    # Plain-text fallback: join all section values
    text = "\n\n".join(str(v) for k, v in sections.items() if v and k != "subject")

    gmail_address = cfg.get("gmail_address", "")
    provider = cfg.get("email_provider", "gmail")

    if provider == "sendgrid" and cfg.get("sendgrid_api_key"):
        ok = await send_via_sendgrid(
            api_key=cfg["sendgrid_api_key"],
            from_email=cfg.get("sendgrid_from_email", gmail_address),
            from_name=cfg.get("sendgrid_from_name", "DNA Compliance"),
            to_addresses=[to_address],
            reply_to=gmail_address,
            subject=subject,
            html_body=html,
            text_body=text,
        )
    else:
        ok = await send_via_gmail_smtp(
            gmail_address=gmail_address,
            gmail_app_password=cfg.get("gmail_app_password", ""),
            to_addresses=[to_address],
            reply_to=gmail_address,
            subject=subject,
            html_body=html,
            text_body=text,
        )

    if ok:
        logger.info(f"Notification email sent to {to_address} (subject: {subject})")
    else:
        logger.warning(f"Notification email delivery failed to {to_address}")
    return ok
