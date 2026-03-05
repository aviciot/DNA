"""
Email Listener — IMAP polling
==============================
Polls Gmail inbox for unseen emails, identifies campaign tokens
from Reply-To / To address, pushes to processing queue.
"""
import asyncio
import email as email_lib
import imaplib
import logging
import re
from email.header import decode_header, make_header

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r'collect_([a-zA-Z0-9]{16,64})', re.IGNORECASE)


def _decode_header_value(val: str | None) -> str:
    if not val:
        return ""
    try:
        return str(make_header(decode_header(val)))
    except Exception:
        return val or ""


def _extract_token_from_headers(msg) -> str | None:
    """Look for collect_TOKEN in To, Delivered-To, and X-Original-To headers."""
    for header in ("To", "Delivered-To", "X-Original-To"):
        value = msg.get(header, "")
        m = _TOKEN_RE.search(value)
        if m:
            return m.group(1)
    return None


def _get_body(msg) -> tuple[str, str]:
    """Extract plain text and HTML body from email."""
    text_body = ""
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if ctype == "text/plain" and not text_body:
                payload = part.get_payload(decode=True)
                if payload:
                    text_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif ctype == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    html_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            text_body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return text_body, html_body


def _get_attachments(msg, storage_base: str, log_id: str) -> list:
    """Save attachments to disk and return metadata list."""
    import os, uuid
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()
        if not filename:
            continue
        filename = _decode_header_value(filename)
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        ctype = part.get_content_type()
        # Save file
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        dir_path = os.path.join(storage_base, "emails", log_id)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, safe_name)
        with open(file_path, "wb") as f:
            f.write(payload)
        attachments.append({
            "filename": filename,
            "content_type": ctype,
            "size_bytes": len(payload),
            "storage_path": file_path,
        })
        logger.debug(f"Saved attachment {filename} → {file_path}")
    return attachments


class IMAPListener:
    def __init__(self, cfg: dict, on_email_callback):
        self.cfg = cfg
        self.on_email = on_email_callback  # async fn(parsed_email: dict)
        self._running = False

    async def poll_once(self, customer_storage_base: str) -> int:
        """Connect, fetch UNSEEN, process each, return count processed."""
        host = self.cfg.get("imap_host", "imap.gmail.com")
        port = self.cfg.get("imap_port", 993)
        gmail_address = self.cfg.get("gmail_address", "")
        app_password = self.cfg.get("gmail_app_password", "")

        if not gmail_address or not app_password:
            logger.warning("IMAP: gmail_address or gmail_app_password not configured")
            return 0

        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(gmail_address, app_password)
            mail.select("inbox")

            status, data = mail.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                mail.logout()
                return 0

            msg_ids = data[0].split()
            logger.info(f"IMAP: {len(msg_ids)} unseen email(s)")
            count = 0

            for msg_id in msg_ids:
                try:
                    _, msg_data = mail.fetch(msg_id, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw)

                    token = _extract_token_from_headers(msg)
                    from_email = _decode_header_value(msg.get("From", ""))
                    subject = _decode_header_value(msg.get("Subject", ""))
                    text_body, html_body = _get_body(msg)

                    parsed = {
                        "token": token,
                        "from_email": from_email,
                        "subject": subject,
                        "body_text": text_body,
                        "body_html": html_body,
                        "_msg": msg,  # raw msg passed to on_email; attachments saved only after customer match
                    }

                    # Mark as SEEN
                    mail.store(msg_id, "+FLAGS", "\\Seen")

                    await self.on_email(parsed)
                    count += 1

                except Exception as e:
                    logger.error(f"IMAP: failed to process msg {msg_id}: {e}")

            mail.logout()
            return count

        except Exception as e:
            logger.error(f"IMAP poll error: {e}")
            return 0

    async def run_forever(self, customer_storage_base: str, interval_seconds: int = 60):
        self._running = True
        logger.info(f"IMAP listener started, polling every {interval_seconds}s")
        while self._running:
            try:
                count = await self.poll_once(customer_storage_base)
                if count:
                    logger.info(f"IMAP: processed {count} email(s)")
            except Exception as e:
                logger.error(f"IMAP listener error: {e}")
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self._running = False
