"""
Attachment Security — mirrors customer-portal/backend/app/upload.py
====================================================================
Validates email attachments through the same security layers as portal uploads:
  Layer 1 — file size limit
  Layer 2 — extension blocklist
  Layer 3 — MIME / magic-bytes validation (python-magic)
  Layer 4 — ClamAV antivirus scan (instream over network socket)

Returns (is_safe: bool, rejection_reason: str).
All checks are synchronous (email_listener is not async).
"""
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Mirrors upload.py exactly ─────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff",
    ".txt", ".csv", ".zip",
}

BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".psm1", ".psd1",
    ".js", ".ts", ".py", ".rb", ".php", ".pl", ".lua",
    ".jar", ".war", ".class", ".dll", ".so", ".dylib",
    ".msi", ".deb", ".rpm", ".dmg", ".app",
    ".vbs", ".wsf", ".hta", ".scr", ".com", ".pif",
    ".html", ".htm", ".svg",
}

MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/zip": ".zip",
}

MAX_ATTACHMENT_MB = int(os.getenv("MAX_ATTACHMENT_SIZE_MB", "20"))
CLAMAV_HOST = os.getenv("CLAMAV_HOST", "portal-clamav")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
REQUIRE_AV_SCAN = os.getenv("REQUIRE_AV_SCAN", "false").lower() == "true"


def scan_attachment(payload: bytes, filename: str, claimed_content_type: str = "") -> tuple[bool, str]:
    """
    Run all security layers on raw attachment bytes.
    Returns (True, "") if safe, (False, reason) if rejected.
    """
    # Layer 1 — size
    max_bytes = MAX_ATTACHMENT_MB * 1024 * 1024
    if len(payload) > max_bytes:
        return False, f"File too large ({len(payload) // (1024*1024)} MB > {MAX_ATTACHMENT_MB} MB limit)"

    # Layer 2 — extension blocklist
    original_ext = Path(filename).suffix.lower()
    if original_ext in BLOCKED_EXTENSIONS:
        return False, f"Blocked extension: {original_ext}"

    # Layers 3 + 4 require a temp file
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="att_sec_")
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(payload)

        # Layer 3 — MIME / magic bytes
        try:
            import magic
            real_mime = magic.from_file(tmp_path, mime=True)
        except Exception as e:
            logger.warning(f"python-magic unavailable, skipping MIME check: {e}")
            real_mime = claimed_content_type or "application/octet-stream"

        safe_ext = MIME_TO_EXT.get(real_mime)
        if not safe_ext:
            return False, f"File type not allowed (detected: {real_mime})"
        if safe_ext not in ALLOWED_EXTENSIONS:
            return False, f"File type not allowed (ext: {safe_ext})"

        # Layer 4 — ClamAV
        clean, av_reason = _clamav_scan(tmp_path)
        if not clean:
            return False, av_reason

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return True, ""


def _clamav_scan(filepath: str) -> tuple[bool, str]:
    """Returns (True, "") if clean. (False, reason) if infected or error + required."""
    try:
        import clamd
        cd = clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT)
        with open(filepath, "rb") as f:
            result = cd.instream(f)
        status, detail = result.get("stream", ("ERROR", "unknown"))
        if status == "OK":
            return True, ""
        return False, f"AV scan rejected: {detail}"
    except Exception as e:
        if REQUIRE_AV_SCAN:
            return False, f"AV scan unavailable (required): {e}"
        logger.warning(f"ClamAV unavailable, skipping scan (REQUIRE_AV_SCAN=false): {e}")
        return True, ""
