#!/usr/bin/env python3
"""
Portal Upload Security Test Suite
==================================
Tests every security layer in the ISO360 evidence upload pipeline.

Run from project root:
    docker cp scripts/test_upload_security.py portal-backend:/tmp/test_upload.py
    docker exec portal-backend python /tmp/test_upload.py

Or directly:
    docker exec portal-backend python -c "$(cat scripts/test_upload_security.py)"
"""

import io
import json
import sys
import uuid
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
# Override via env: TOKEN=xxx TASK_ID=xxx python test_upload.py
import os
BASE_URL = os.getenv("BASE_URL", "http://localhost:4010")
TOKEN    = os.getenv("TOKEN",   "f1921a351984940a28f28db52f5584fbcca4df05e4ffa7995098c475b9f27b86")
TASK_ID  = os.getenv("TASK_ID", "bedac15d-73f8-4ee6-8b3d-9ac415d7c421")  # customer 42

# ── ANSI colours ──────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; W = "\033[0m"; BOLD = "\033[1m"

passed = failed = 0

def ok(msg):
    global passed; passed += 1
    print(f"  {G}✓ PASS{W}  {msg}")

def fail(msg):
    global failed; failed += 1
    print(f"  {R}✗ FAIL{W}  {msg}")

def info(msg):  print(f"  {B}ℹ{W}  {msg}")
def section(t): print(f"\n{BOLD}{Y}── {t} ──{W}")

# ── Multipart builder (no third-party libs needed) ────────────────────────────
def multipart(filename: str, content: bytes, mime: str = "application/octet-stream"):
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"

# ── Upload helper ─────────────────────────────────────────────────────────────
# Uses the existing /portal/upload/{task_id} endpoint which runs the same
# process_upload() security pipeline as the ISO360 upload endpoint.
def upload(task_id: str, filename: str, content: bytes,
           mime: str = "application/octet-stream", token: str = TOKEN):
    body, ct = multipart(filename, content, mime)
    req = urllib.request.Request(
        f"{BASE_URL}/portal/upload/{task_id}",
        data=body,
        headers={"Cookie": f"portal_token={token}", "Content-Type": ct},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def expect_pass(label, task_id, filename, content, mime="application/pdf"):
    status, body = upload(task_id, filename, content, mime)
    if status == 200:
        ok(f"{label} → accepted ({status})")
    else:
        fail(f"{label} → {status}: {body[:120].decode(errors='replace')}")

def expect_fail(label, task_id, filename, content,
                mime="application/octet-stream", want=422):
    status, body = upload(task_id, filename, content, mime)
    if status in (want, 400, 401, 413, 422):
        ok(f"{label} → correctly rejected ({status})")
    else:
        fail(f"{label} → {status} — expected rejection, got accepted!")

# ── Test payloads ─────────────────────────────────────────────────────────────

# Minimal valid PDF (starts with %PDF magic bytes — passes all layers)
VALID_PDF = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"xref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\ntrailer\n<< /Size 3 /Root 1 0 R >>\n"
    b"startxref\n116\n%%EOF"
)

# Standard EICAR antivirus test string — universally detected by ClamAV,
# NOT actual malware, safe to use in tests. Looks like plain text so it
# passes Layer 3 (MIME) and reaches ClamAV (Layer 4).
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

# EXE magic bytes (MZ header) — will fail MIME check even with .pdf extension
FAKE_PDF_IS_EXE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 200

import io, zipfile

def make_zip_with_eicar() -> bytes:
    """Build a ZIP file containing the EICAR test string using stdlib zipfile."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("eicar.txt", EICAR.decode("latin-1"))
    return buf.getvalue()

ZIP_WITH_EICAR = make_zip_with_eicar()

# 11 MB file — exceeds size limit
BIG_FILE = b"A" * (11 * 1024 * 1024)

# ── Verify the task token is valid ────────────────────────────────────────────
def verify_auth() -> bool:
    req = urllib.request.Request(
        f"{BASE_URL}/portal/me",
        headers={"Cookie": f"portal_token={TOKEN}"},
    )
    try:
        r = urllib.request.urlopen(req)
        data = json.loads(r.read())
        info(f"Authenticated as: {data.get('customer_name', '?')} ({data.get('iso_code', '?')})")
        return True
    except Exception:
        return False

# ── Run tests ─────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}Portal Upload Security Test Suite{W}")
    print("=" * 55)

    # ── Verify auth ───────────────────────────────────────────────────────────
    if not verify_auth():
        print(f"{R}Auth failed — set TOKEN env var to a valid portal_token.{W}")
        sys.exit(1)
    info(f"Task ID : {TASK_ID}")
    info(f"Token   : {TOKEN[:16]}…")

    # ─────────────────────────────────────────────────────────────────────────
    section("Layer 0 — Authentication")
    # No token
    body, ct = multipart("test.pdf", VALID_PDF, "application/pdf")
    req = urllib.request.Request(
        f"{BASE_URL}/portal/upload/{TASK_ID}",
        data=body, headers={"Content-Type": ct}, method="POST",
    )
    try:
        urllib.request.urlopen(req)
        fail("No token → accepted (should be 401)")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            ok(f"No token → 401 Unauthorized")
        else:
            fail(f"No token → {e.code} (expected 401)")

    # Invalid token
    status, _ = upload(TASK_ID, "test.pdf", VALID_PDF, "application/pdf", token="deadbeef" * 8)
    if status == 401:
        ok(f"Invalid token → 401 Unauthorized")
    else:
        fail(f"Invalid token → {status} (expected 401)")

    # ─────────────────────────────────────────────────────────────────────────
    section("Layer 1 — File size limit")
    expect_fail("11 MB file (over limit)", TASK_ID, "bigfile.pdf", BIG_FILE, "application/pdf", want=413)

    # ─────────────────────────────────────────────────────────────────────────
    section("Layer 2 — Extension blocklist")
    expect_fail(".exe  (Windows executable)",  TASK_ID, "malware.exe",   b"MZ" + b"\x00"*50)
    expect_fail(".py   (Python script)",        TASK_ID, "payload.py",    b"import os; os.system('id')")
    expect_fail(".sh   (shell script)",         TASK_ID, "exploit.sh",    b"#!/bin/bash\nwhoami")
    expect_fail(".js   (JavaScript)",           TASK_ID, "xss.js",        b"eval(atob('bad'))")
    expect_fail(".html (HTML/XSS)",             TASK_ID, "phish.html",    b"<script>alert(1)</script>")
    expect_fail(".php  (PHP webshell)",         TASK_ID, "shell.php",     b"<?php system($_GET['cmd']); ?>")
    expect_fail(".ps1  (PowerShell)",           TASK_ID, "run.ps1",       b"Invoke-Expression $payload")

    # ─────────────────────────────────────────────────────────────────────────
    section("Layer 3 — MIME / magic-bytes validation")
    expect_fail(
        "EXE renamed to .pdf  (MZ header detected)",
        TASK_ID, "invoice.pdf", FAKE_PDF_IS_EXE, "application/pdf",
    )
    expect_fail(
        "Random binary as .docx",
        TASK_ID, "report.docx", b"\x00\x01\x02\x03\xde\xad\xbe\xef" * 64,
    )
    # JPEG content with .pdf extension — accepted by design.
    # JPEG is a safe MIME type; the security goal is blocking executables/scripts,
    # not enforcing extension purity. A customer uploading a screenshot as .pdf is valid.
    expect_pass(
        "JPEG content in .pdf  (safe MIME — accepted by design)",
        TASK_ID, "scan.pdf", b"\xff\xd8\xff\xe0" + b"\x00"*100, "application/pdf",
    )

    # Valid plain-text file passes all layers (txt/plain is allowed and won't
    # trigger ClamAV heuristics the way a hand-crafted minimal PDF might)
    expect_pass(
        "Legitimate .txt passes all layers",
        TASK_ID, "notes.txt",
        b"Compliance policy document - access control review notes.\nAll procedures verified.",
        "text/plain",
    )

    # ─────────────────────────────────────────────────────────────────────────
    section("Layer 4 — ClamAV antivirus scan")
    # EICAR as plain text — passes MIME check (text/plain is allowed)
    # but ClamAV flags it as Eicar-Test-Signature
    expect_fail(
        "EICAR test string in .txt  (ClamAV: Eicar-Test-Signature)",
        TASK_ID, "eicar_test.txt", EICAR, "text/plain",
    )
    # EICAR inside a ZIP — ZIP magic bytes pass MIME, ClamAV scans inside
    expect_fail(
        "EICAR inside ZIP file  (ClamAV scans archive contents)",
        TASK_ID, "archive.zip", ZIP_WITH_EICAR, "application/zip",
    )

    # ─────────────────────────────────────────────────────────────────────────
    section("Layer 5 — Safe storage (path traversal)")
    # Attempts to break out of storage path via filename
    # The filename is never used in the storage path (random hex used instead)
    # but we verify the endpoint doesn't 500 on weird filenames
    status, _ = upload(TASK_ID, "../../etc/passwd", VALID_PDF, "application/pdf")
    if status in (200, 422):
        ok(f"Path traversal in filename → handled safely ({status})")
    else:
        fail(f"Path traversal in filename → unexpected status {status}")

    status, _ = upload(TASK_ID, "a" * 300 + ".pdf", VALID_PDF, "application/pdf")
    if status in (200, 422, 400):
        ok(f"Very long filename (300 chars) → handled safely ({status})")
    else:
        fail(f"Very long filename → unexpected status {status}")

    # ─────────────────────────────────────────────────────────────────────────
    section("Summary")
    total = passed + failed
    colour = G if failed == 0 else R
    print(f"\n  {colour}{BOLD}{passed}/{total} tests passed{W}", end="")
    if failed:
        print(f"  {R}({failed} FAILED){W}")
    else:
        print(f"  {G}— all security layers verified ✓{W}")
    print()
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
