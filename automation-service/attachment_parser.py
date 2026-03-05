"""
Attachment Parser
=================
Extracts text (or base64 image) from email attachments.
Supports: PDF, DOCX, XLSX, plain text, images.
"""
import base64
import logging
import os

logger = logging.getLogger(__name__)


def parse_attachment(storage_path: str, content_type: str, filename: str) -> dict:
    """
    Parse an attachment file and return:
    {
        "type": "text" | "image",
        "content": str,          # extracted text or base64
        "mime": str,             # original MIME type
        "filename": str,
    }
    """
    ext = os.path.splitext(filename)[1].lower()

    try:
        if content_type == "application/pdf" or ext == ".pdf":
            return {"type": "text", "content": _extract_pdf(storage_path), "mime": content_type, "filename": filename}

        if content_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) or ext == ".docx":
            return {"type": "text", "content": _extract_docx(storage_path), "mime": content_type, "filename": filename}

        if content_type in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",) or ext in (".xlsx", ".xls"):
            return {"type": "text", "content": _extract_excel(storage_path), "mime": content_type, "filename": filename}

        if content_type.startswith("image/") or ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            return {"type": "image", "content": _encode_image(storage_path), "mime": content_type, "filename": filename}

        if content_type.startswith("text/") or ext in (".txt", ".csv", ".md"):
            with open(storage_path, "r", encoding="utf-8", errors="replace") as f:
                return {"type": "text", "content": f.read()[:20000], "mime": content_type, "filename": filename}

        logger.warning(f"Unsupported attachment type: {content_type} / {ext}")
        return {"type": "unsupported", "content": "", "mime": content_type, "filename": filename}

    except Exception as e:
        logger.error(f"Failed to parse attachment {filename}: {e}")
        return {"type": "error", "content": str(e), "mime": content_type, "filename": filename}


def _extract_pdf(path: str) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n\n".join(text_parts)[:30000]
    except ImportError:
        # Fallback: read raw bytes and try to extract ASCII
        with open(path, "rb") as f:
            raw = f.read()
        import re
        text = re.sub(rb'[^\x20-\x7e\n\t]', b' ', raw).decode("ascii", errors="ignore")
        return " ".join(text.split())[:10000]


def _extract_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:30000]


def _extract_excel(path: str) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines = []
    for sheet in wb.worksheets:
        lines.append(f"[Sheet: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(c.strip() for c in cells):
                lines.append("\t".join(cells))
    return "\n".join(lines)[:20000]


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()
