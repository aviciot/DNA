"""
Full Cleanup: Wipe all customers, ISO plans, templates, and ISO standards.
Use this before re-running the ISO build with the new placeholder_dictionary architecture.

Usage:
  python cleanup_all.py --dry-run     # preview what will be deleted
  python cleanup_all.py               # execute full wipe
  python cleanup_all.py --keep-auth   # keep auth.users (default: keep)
"""

import argparse
import psycopg2
import sys

DB = dict(host="localhost", port=3012, dbname="dna", user="dna_user", password="dna_password_dev")

# Deletion order: children before parents, respecting FK constraints
STEPS = [
    # --- Customer data ---
    ("customer_task_resolutions",   "task_id IN (SELECT id FROM dna_app.customer_tasks WHERE customer_id IN (SELECT id FROM dna_app.customers))"),
    ("customer_tasks",              "customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customer_placeholders",       "customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customer_profile_data",       "customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customer_documents",          "customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customer_iso_plan_templates", "plan_id IN (SELECT id FROM dna_app.customer_iso_plans)"),
    ("iso_placeholder_dictionary",  "plan_id IN (SELECT id FROM dna_app.customer_iso_plans)"),
    ("customer_iso_plans",          "customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customer_collection_channels","customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customer_configuration",      "customer_id IN (SELECT id FROM dna_app.customers)"),
    ("customers",                   "1=1"),
    ("notification_reads",           "1=1"),
    ("notifications",                "1=1"),
    # --- Templates & ISO standards ---
    ("template_versions",           "1=1"),
    ("template_iso_mapping",        "1=1"),
    ("ai_tasks",                    "task_type = 'iso_build'"),
    ("templates",                   "1=1"),
    ("template_files",              "1=1"),
    ("iso_standards",               "1=1"),
]


def run(dry_run: bool):
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Full cleanup starting...\n")
    total = 0

    for table, where in STEPS:
        # Skip iso_placeholder_dictionary if it doesn't exist yet
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='dna_app' AND table_name=%s)",
            (table,)
        )
        if not cur.fetchone()[0]:
            print(f"  {'skip (table not found)':25s}  {table}")
            continue

        cur.execute(f"SELECT COUNT(*) FROM dna_app.{table} WHERE {where}")
        count = cur.fetchone()[0]
        if count:
            print(f"  {'would delete' if dry_run else 'deleted':15s} {count:5d} row(s)  ->  {table}")
            if not dry_run:
                cur.execute(f"DELETE FROM dna_app.{table} WHERE {where}")
            total += count
        else:
            print(f"  {'skip (empty)':25s}  {table}")

    if dry_run:
        conn.rollback()
        print(f"\n[DRY RUN] Would delete {total} total rows. Nothing changed.")
    else:
        conn.commit()
        print(f"\nDone. {total} total rows deleted.")
        _verify()

    cur.close()
    conn.close()


def _verify():
    print("\n[Verify] Checking all tables are empty...\n")
    conn2 = psycopg2.connect(**DB)
    cur2 = conn2.cursor()
    tables = [t for t, _ in STEPS]
    all_clean = True
    for table in tables:
        cur2.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='dna_app' AND table_name=%s)",
            (table,)
        )
        if not cur2.fetchone()[0]:
            continue
        cur2.execute(f"SELECT COUNT(*) FROM dna_app.{table}")
        count = cur2.fetchone()[0]
        status = "CLEAN" if count == 0 else f"FAIL ({count} rows remain)"
        print(f"  {status:30s}  {table}")
        if count > 0:
            all_clean = False
    cur2.close()
    conn2.close()
    print(f"\n{'ALL CLEAN' if all_clean else 'WARNING: some data remains'}")
    if not all_clean:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()

    print("WARNING: This will delete ALL customers, ISO plans, templates, and ISO standards.")
    if not args.dry_run:
        confirm = input("Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    run(dry_run=args.dry_run)
