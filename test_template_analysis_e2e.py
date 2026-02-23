#!/usr/bin/env python3
"""
Complete E2E Test for Template Analysis Workflow
================================================
Tests: Login → Upload Document → Analyze → Verify Results

Usage:
    python test_template_analysis_e2e.py <path_to_docx_file>

If no file provided, will look for ISMS 20 in common locations.
"""

import requests
import time
import json
import sys
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8400"
AUTH_BASE = "http://localhost:8401"
EMAIL = "admin@dna.local"
PASSWORD = "admin123"

def log(message, level="INFO"):
    """Print formatted log message."""
    timestamp = time.strftime("%H:%M:%S")
    # Handle encoding issues on Windows console
    try:
        print(f"[{timestamp}] [{level}] {message}")
    except UnicodeEncodeError:
        # Replace problematic characters with ASCII equivalents
        safe_message = message.encode('ascii', errors='replace').decode('ascii')
        print(f"[{timestamp}] [{level}] {safe_message}")

def find_test_document():
    """Find existing DOCX file for testing."""
    log("Looking for test document...")

    # Check command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if Path(file_path).exists():
            log(f"OK Using provided file: {file_path}")
            return file_path
        else:
            log(f"FAIL Provided file not found: {file_path}", "ERROR")

    # Common locations to check
    common_paths = [
        "C:\\Users\\acohen.SHIFT4CORP\\Desktop\\ISMS 20.docx",
        "C:\\Users\\acohen.SHIFT4CORP\\Desktop\\ISMS 20 Patch Management.docx",
        "C:\\Users\\acohen.SHIFT4CORP\\Downloads\\ISMS 20.docx",
    ]

    for path in common_paths:
        if Path(path).exists():
            log(f"OK Found test document: {path}")
            return path

    log("FAIL No test document found. Please provide path as argument:", "ERROR")
    log(f"   Usage: python {sys.argv[0]} <path_to_docx_file>", "ERROR")
    return None

def test_login():
    """Test login and return access token."""
    log("Testing login...")

    response = requests.post(
        f"{AUTH_BASE}/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10
    )

    if response.status_code != 200:
        log(f"FAIL Login failed: {response.status_code} - {response.text}", "ERROR")
        return None

    data = response.json()
    token = data.get("access_token")
    log(f"OK Login successful, token: {token[:50]}...")
    return token

def test_upload_document(token, file_path):
    """Upload document and return file ID."""
    log(f"Uploading document: {file_path}...")

    with open(file_path, 'rb') as f:
        files = {'file': ('test_template.docx', f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
        data = {'file_type': 'reference'}

        response = requests.post(
            f"{API_BASE}/api/v1/template-files/upload",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )

    if response.status_code == 409:
        # File already exists - extract ID from error message
        import re
        error_text = response.text
        match = re.search(r"ID: ([a-f0-9\-]{36})", error_text)
        if match:
            file_id = match.group(1)
            log(f"OK File already exists, reusing file_id: {file_id}")
            return file_id
        else:
            log(f"FAIL Could not extract file ID from 409 response: {error_text}", "ERROR")
            return None

    if response.status_code not in [200, 201]:
        log(f"FAIL Upload failed: {response.status_code} - {response.text}", "ERROR")
        return None

    data = response.json()
    file_id = data.get("id")
    log(f"OK Upload successful, file_id: {file_id}")
    return file_id

def test_analyze(token, file_id):
    """Trigger analysis and return task ID."""
    log(f"Triggering analysis for file: {file_id}...")

    response = requests.post(
        f"{API_BASE}/api/v1/template-analysis/analyze",
        json={"template_file_id": file_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )

    if response.status_code != 200:
        log(f"FAIL Analysis trigger failed: {response.status_code} - {response.text}", "ERROR")
        return None

    data = response.json()
    task_id = data.get("task_id")
    log(f"OK Analysis queued, task_id: {task_id}")
    return task_id

def poll_task_status(token, task_id, max_wait=120):
    """Poll task status until complete or timeout."""
    log(f"Polling task status (max {max_wait}s)...")

    start_time = time.time()
    last_status = None
    last_progress = None

    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{API_BASE}/api/v1/template-analysis/tasks/{task_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )

        if response.status_code != 200:
            log(f"FAIL Status check failed: {response.status_code}", "ERROR")
            return None

        data = response.json()
        status = data.get("status")
        progress = data.get("progress", 0)

        # Only log if status or progress changed
        if status != last_status or progress != last_progress:
            log(f"  Status: {status}, Progress: {progress}%")
            last_status = status
            last_progress = progress

        if status == "completed":
            log("OK Task completed successfully")
            return data
        elif status == "failed":
            error = data.get("error", "Unknown error")
            log(f"FAIL Task failed: {error}", "ERROR")
            return None

        time.sleep(2)

    log(f"FAIL Timeout waiting for task completion", "ERROR")
    return None

def verify_recommendations(token, file_id):
    """Get and verify AI recommendations."""
    log(f"Fetching recommendations for file: {file_id}...")

    response = requests.get(
        f"{API_BASE}/api/v1/template-analysis/{file_id}/recommendations",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )

    if response.status_code != 200:
        log(f"FAIL Failed to fetch recommendations: {response.status_code} - {response.text}", "ERROR")
        return False

    data = response.json()
    replacements = data.get("replacements", [])

    log(f"OK Received {len(replacements)} placeholder recommendations:")
    for i, rec in enumerate(replacements, 1):
        log(f"  {i}. '{rec['original_text']}' -> {rec['placeholder']}")
        log(f"     Question: {rec['question']}")

    return len(replacements) > 0

def verify_database(file_id, task_id):
    """Verify data in database using docker exec."""
    log("Verifying database records...")

    import subprocess

    try:
        # Check template_files table
        result = subprocess.run([
            "docker-compose", "exec", "-T", "dna-postgres",
            "psql", "-U", "dna_user", "-d", "dna",
            "-c", f"SELECT id, filename, status FROM dna_app.template_files WHERE id='{file_id}';"
        ], capture_output=True, text=True, cwd="C:\\Users\\acohen.SHIFT4CORP\\Desktop\\PythonProjects\\MCP Performance\\DNA\\dashboard")

        if file_id in result.stdout:
            log("OK Template file record found in database")
        else:
            log("FAIL Template file not found in database", "ERROR")
            return False

        # Check ai_tasks table
        result = subprocess.run([
            "docker-compose", "exec", "-T", "dna-postgres",
            "psql", "-U", "dna_user", "-d", "dna",
            "-c", f"SELECT id, status, task_type FROM dna_app.ai_tasks WHERE id='{task_id}';"
        ], capture_output=True, text=True, cwd="C:\\Users\\acohen.SHIFT4CORP\\Desktop\\PythonProjects\\MCP Performance\\DNA\\dashboard")

        if task_id in result.stdout and "completed" in result.stdout:
            log("OK AI task record found in database with status 'completed'")
        else:
            log("FAIL AI task not completed in database", "ERROR")
            return False

        return True

    except Exception as e:
        log(f"FAIL Database verification failed: {e}", "ERROR")
        return False

def check_logs():
    """Check backend and AI service logs for errors."""
    log("Checking service logs...")

    import subprocess

    try:
        # Check backend logs
        result = subprocess.run([
            "docker-compose", "logs", "--tail=50", "dna-backend"
        ], capture_output=True, text=True, cwd="C:\\Users\\acohen.SHIFT4CORP\\Desktop\\PythonProjects\\MCP Performance\\DNA\\dashboard")

        if "ERROR" in result.stdout or "Exception" in result.stdout:
            log("WARN Errors found in backend logs", "WARN")
        else:
            log("OK Backend logs clean (no errors)")

        # Check AI service logs
        result = subprocess.run([
            "docker-compose", "logs", "--tail=50", "dna-ai-service"
        ], capture_output=True, text=True, cwd="C:\\Users\\acohen.SHIFT4CORP\\Desktop\\PythonProjects\\MCP Performance\\DNA\\dashboard")

        if "ERROR" in result.stdout or "Exception" in result.stdout:
            log("WARN Errors found in AI service logs", "WARN")
        else:
            log("OK AI service logs clean (no errors)")

        return True

    except Exception as e:
        log(f"FAIL Log check failed: {e}", "ERROR")
        return False

def main():
    """Run complete E2E test."""
    print("\n" + "="*70)
    print("TEMPLATE ANALYSIS E2E TEST")
    print("="*70 + "\n")

    file_path = None
    cleanup_file = False

    try:
        # Step 1: Find test document
        file_path = find_test_document()
        if not file_path:
            return False

        # Step 2: Login
        token = test_login()
        if not token:
            log("FAIL Test failed at login step", "ERROR")
            return False

        # Step 3: Upload document
        file_id = test_upload_document(token, file_path)
        if not file_id:
            log("FAIL Test failed at upload step", "ERROR")
            return False

        # Step 4: Trigger analysis
        task_id = test_analyze(token, file_id)
        if not task_id:
            log("FAIL Test failed at analysis trigger step", "ERROR")
            return False

        # Step 5: Wait for completion
        task_result = poll_task_status(token, task_id)
        if not task_result:
            log("FAIL Test failed during analysis execution", "ERROR")
            return False

        # Step 6: Verify recommendations
        if not verify_recommendations(token, file_id):
            log("FAIL Test failed at recommendations verification", "ERROR")
            return False

        # Step 7: Verify database
        if not verify_database(file_id, task_id):
            log("FAIL Test failed at database verification", "ERROR")
            return False

        # Step 8: Check logs
        check_logs()

        print("\n" + "="*70)
        print("OK ALL TESTS PASSED!")
        print("="*70 + "\n")
        print(f"File ID: {file_id}")
        print(f"Task ID: {task_id}")
        print("\nYou can now safely test through the UI.")
        print("="*70 + "\n")

        return True

    except Exception as e:
        log(f"FAIL Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Don't delete the file - we're using an existing one
        pass

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
