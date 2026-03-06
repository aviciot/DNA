"""
Customer Portal smoke test.
Usage: python test/test_portal.py [token]
"""
import sys
import subprocess
import requests
import io

BACKEND = "http://localhost:4010"
FRONTEND = "http://localhost:4000"


def get_token_from_db():
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "dna-postgres",
         "psql", "-U", "dna_user", "-d", "dna",
         "-c", """SELECT ecr.token FROM dna_app.email_collection_requests ecr
                  JOIN dna_app.customers c ON c.id = ecr.customer_id
                  JOIN dna_app.customer_iso_plans cip ON cip.id = ecr.plan_id
                  JOIN dna_app.iso_standards iso ON iso.id = cip.iso_standard_id
                  WHERE ecr.status='pending' AND ecr.expires_at > NOW() LIMIT 1;""",
         "-t", "-A"],
        capture_output=True, text=True,
        cwd=r"c:\Users\acohen.SHIFT4CORP\Desktop\PythonProjects\MCP Performance\DNA"
    )
    token = result.stdout.strip()
    if not token:
        print("[ERROR] No valid token with complete data in DB")
        sys.exit(1)
    return token


def get_evidence_task(customer_id):
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "dna-postgres",
         "psql", "-U", "dna_user", "-d", "dna",
         "-c", f"SELECT id FROM dna_app.customer_tasks WHERE customer_id={customer_id} AND requires_evidence=true AND status='pending' LIMIT 1;",
         "-t", "-A"],
        capture_output=True, text=True,
        cwd=r"c:\Users\acohen.SHIFT4CORP\Desktop\PythonProjects\MCP Performance\DNA"
    )
    return result.stdout.strip()


def ok(label): print(f"  [OK]   {label}")
def fail(label, detail=""): print(f"  [FAIL] {label} {detail}")


def run(token):
    print(f"\nToken: {token}\n")
    session = requests.Session()

    # 1. Backend health
    r = requests.get(f"{BACKEND}/health")
    ok("Backend /health") if r.status_code == 200 else fail("Backend /health", r.status_code)

    # 2. Auth
    r = session.get(f"{BACKEND}/portal/auth?token={token}", allow_redirects=False)
    if r.status_code in (302, 307) and "portal_token" in r.cookies:
        ok("Auth: cookie set + redirect")
        session.cookies.set("portal_token", r.cookies["portal_token"], domain="localhost")
    else:
        fail("Auth", f"status={r.status_code} cookies={dict(r.cookies)}")
        return

    # 3. /me
    r = session.get(f"{BACKEND}/portal/me")
    if r.status_code == 200:
        me = r.json()
        ok(f"/me -> {me.get('customer_name')} | {me.get('iso_code')}")
        customer_id = None
        # get customer_id from DB for task lookup
    else:
        fail("/me", f"{r.status_code} {r.text}")
        return

    # 4. /progress
    r = session.get(f"{BACKEND}/portal/progress")
    if r.status_code == 200:
        p = r.json()
        ok(f"/progress -> {p.get('completed')}/{p.get('total')} ({p.get('percentage')}%)")
    else:
        fail("/progress", f"{r.status_code} {r.text}")

    # 5. /questions
    r = session.get(f"{BACKEND}/portal/questions")
    if r.status_code == 200:
        questions = r.json()
        ok(f"/questions -> {len(questions)} tasks")
    else:
        fail("/questions", f"{r.status_code} {r.text}")
        questions = []

    # 6. Upload test - find a task that requires evidence
    evidence_tasks = [q for q in questions if q.get("requires_evidence") and q.get("status") == "pending"]
    if evidence_tasks:
        task_id = evidence_tasks[0]["id"]
        # Valid PDF magic bytes (libmagic checks the header)
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 1 >>\nstartxref\n9\n%%EOF"
        r = session.post(
            f"{BACKEND}/portal/upload/{task_id}",
            files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        if r.status_code == 200:
            ok(f"Upload -> {r.json().get('filename')}")
        else:
            fail("Upload", f"{r.status_code} {r.text}")
    else:
        print("  [SKIP] Upload (no pending evidence tasks)")

    # 7. /history
    r = session.get(f"{BACKEND}/portal/history")
    ok(f"/history -> {len(r.json())} events") if r.status_code == 200 else fail("/history", r.status_code)

    # 8. Unauthenticated -> 401
    r = requests.get(f"{BACKEND}/portal/me")
    ok("Unauthenticated -> 401") if r.status_code == 401 else fail("Unauthenticated check", f"got {r.status_code}")

    # 9. Frontend reachable
    r = requests.get(FRONTEND, allow_redirects=False)
    ok(f"Frontend reachable (status {r.status_code})") if r.status_code < 500 else fail("Frontend", r.status_code)

    print()


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else get_token_from_db()
    run(token)
