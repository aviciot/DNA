import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import magic
from fastapi import HTTPException, UploadFile

from app.config import settings

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


def _scan_clamav(filepath: str) -> bool:
    """Returns True if clean, False if infected. Raises if unavailable."""
    try:
        import clamd
        cd = clamd.ClamdNetworkSocket(host=settings.clamav_host, port=settings.clamav_port)
        result = cd.scan(filepath)
        if result is None:
            return True
        status = list(result.values())[0][0]
        return status == "OK"
    except Exception as e:
        if settings.require_av_scan:
            raise HTTPException(status_code=503, detail=f"AV scan unavailable: {e}")
        return True  # only if REQUIRE_AV_SCAN=false


async def process_upload(file: UploadFile, customer_id: int, task_id: str) -> dict:
    """Full upload pipeline. Returns storage metadata dict."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    # Layer 1: size check before reading
    content_length = file.size
    if content_length and content_length > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    # Write to temp
    tmp_dir = Path(tempfile.gettempdir()) / "portal_uploads"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{uuid4().hex}"

    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    tmp_path.write_bytes(data)

    try:
        # Layer 3: magic bytes → real mime
        real_mime = magic.from_file(str(tmp_path), mime=True)
        safe_ext = MIME_TO_EXT.get(real_mime)
        if not safe_ext:
            raise HTTPException(status_code=422, detail=f"File type not allowed: {real_mime}")

        # Extension double-check against blocklist
        original_ext = Path(file.filename or "").suffix.lower()
        if original_ext in BLOCKED_EXTENSIONS:
            raise HTTPException(status_code=422, detail="File type not allowed")
        if safe_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=422, detail="File type not allowed")

        # Layer 4: ClamAV
        if not _scan_clamav(str(tmp_path)):
            raise HTTPException(status_code=422, detail="File failed security scan")

        # Layer 5: move to final storage
        dest_dir = Path(settings.storage_path) / "customers" / str(customer_id) / "evidence" / task_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        storage_name = f"{uuid4().hex[:8]}{safe_ext}"
        dest = dest_dir / storage_name
        shutil.move(str(tmp_path), str(dest))

        return {
            "original_filename": file.filename,
            "storage_path": str(dest),
            "storage_name": storage_name,
            "mime_type": real_mime,
            "size_bytes": len(data),
        }
    except HTTPException:
        raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
