"""
Test: Create Customer Flow
Verifies a new customer is correctly populated across all relevant tables.
"""

import requests
import psycopg2
import sys
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
API_URL   = "http://localhost:3010"
AUTH_URL  = "http://localhost:3011"
DB = dict(host="localhost", port=3012, dbname="dna", user="dna_user", password="dna_password_dev")

ADMIN_EMAIL    = "admin@dna.local"
ADMIN_PASSWORD = "admin123"

ISO_STANDARD_ID = "31156ad6-37ff-4efd-8ef9-9eff0500c54f"  # ISO27017_Heb_Legacy (has approved templates)

TEST_CUSTOMER = {
    "name": f"Test Corp {datetime.now().strftime('%H%M%S')}",
    "email": f"test_{datetime.now().strftime('%H%M%S')}@testcorp.com",
    "contact_person": "Test User",
    "phone": "050-0000000",
    "storage_type": "local",
    "portal_enabled": False,
    "iso_assignments": [{
        "iso_standard_id": ISO_STANDARD_ID,
        "template_selection_mode": "all",
        "selected_template_ids": None,
        "target_completion_date": None,
    }]
}

# ── Helpers ───────────────────────────────────────────────────────────────────
ok   = lambda msg: print(f"  ✅ {msg}")
fail = lambda msg: (print(f"  ❌ {msg}"), sys.exit(1))
info = lambda msg: print(f"  ℹ  {msg}")

def check(label, value, expected=None):
    if expected is not None:
        if value != expected:
            fail(f"{label}: expected {expected}, got {value}")
    elif not value:
        fail(f"{label}: got {value!r}")
    ok(f"{label}: {value}")
    return value

# ── Step 1: Get auth token ────────────────────────────────────────────────────
print("\n[1] Auth")
r = requests.post(f"{AUTH_URL}/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
if r.status_code != 200:
    fail(f"Login failed {r.status_code}: {r.text}")
token = r.json()["access_token"]
ok("Login OK")
headers = {"Authorization": f"Bearer {token}"}

# ── Step 2: Create customer via API ──────────────────────────────────────────
print("\n[2] Create Customer API")
r = requests.post(f"{API_URL}/api/v1/iso-customers", json=TEST_CUSTOMER, headers=headers)
if r.status_code != 201:
    fail(f"Create customer failed {r.status_code}: {r.text}")
result = r.json()
customer_id = result["customer"]["id"]
ok(f"Customer created — ID: {customer_id}")

iso_plans = result.get("iso_plans_created", [])
check("ISO plans returned in response", len(iso_plans), 1)
plan_id = iso_plans[0]["plan_id"]
ok(f"Plan ID: {plan_id}")

# ── Step 3: Verify DB ─────────────────────────────────────────────────────────
print("\n[3] DB Verification")
conn = psycopg2.connect(**DB)
cur = conn.cursor()

# customers
cur.execute("SELECT id, name, status, storage_path FROM dna_app.customers WHERE id = %s", (customer_id,))
row = cur.fetchone()
if not row: fail("customers row missing")
ok(f"customers: id={row[0]}, status={row[2]}, storage={row[3]}")

# customer_iso_plans
cur.execute("SELECT id, plan_status FROM dna_app.customer_iso_plans WHERE customer_id = %s", (customer_id,))
row = cur.fetchone()
if not row: fail("customer_iso_plans row missing")
check("customer_iso_plans.plan_status", row[1] in ("active", "generated"), True)

# customer_iso_plan_templates
cur.execute("SELECT COUNT(*) FROM dna_app.customer_iso_plan_templates WHERE plan_id = %s", (plan_id,))
tmpl_count = cur.fetchone()[0]
check("customer_iso_plan_templates count", tmpl_count > 0, True)
info(f"{tmpl_count} template(s) linked to plan")

# customer_documents
cur.execute("SELECT COUNT(*), MIN(status) FROM dna_app.customer_documents WHERE customer_id = %s AND plan_id = %s", (customer_id, plan_id))
doc_row = cur.fetchone()
check("customer_documents count", doc_row[0] > 0, True)
info(f"{doc_row[0]} document(s), status={doc_row[1]}")

# customer_placeholders
cur.execute("SELECT COUNT(*) FROM dna_app.customer_placeholders WHERE customer_id = %s AND plan_id = %s", (customer_id, plan_id))
ph_count = cur.fetchone()[0]
check("customer_placeholders count", ph_count > 0, True)
info(f"{ph_count} placeholder(s) seeded")

# customer_tasks
cur.execute("SELECT COUNT(*) FROM dna_app.customer_tasks WHERE customer_id = %s AND plan_id = %s", (customer_id, plan_id))
task_count = cur.fetchone()[0]
check("customer_tasks count", task_count > 0, True)
info(f"{task_count} task(s) generated")

cur.close()
conn.close()

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ ALL CHECKS PASSED
   Customer ID : {customer_id}
   Plan ID     : {plan_id}
   Templates   : {tmpl_count}
   Documents   : {doc_row[0]}
   Placeholders: {ph_count}
   Tasks       : {task_count}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
