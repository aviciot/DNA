"""
Cleanup: Delete customer and all related data by name or ID.
Usage:
  python cleanup_customer.py --name "Test Corp"
  python cleanup_customer.py --id 42
  python cleanup_customer.py --name "Test Corp" --dry-run
"""

import argparse
import psycopg2
import sys

DB = dict(host="localhost", port=3012, dbname="dna", user="dna_user", password="dna_password_dev")

# Deletion order matters — children before parents
CHILD_TABLES = [
    ("customer_task_resolutions", "task_id",    "customer_tasks",    "id"),
    ("customer_tasks",            "customer_id", None,                None),
    ("customer_placeholders",     "customer_id", None,                None),
    ("customer_profile_data",     "customer_id", None,                None),
    ("customer_documents",        "customer_id", None,                None),
    ("customer_iso_plan_templates","plan_id",    "customer_iso_plans","id"),
    ("customer_iso_plans",        "customer_id", None,                None),
    ("customer_collection_channels","customer_id",None,               None),
    ("customer_configuration",    "customer_id", None,                None),
]

def resolve_customer(cur, name=None, cid=None):
    if cid:
        cur.execute("SELECT id, name FROM dna_app.customers WHERE id = %s", (cid,))
    else:
        cur.execute("SELECT id, name FROM dna_app.customers WHERE name ILIKE %s", (name,))
    rows = cur.fetchall()
    if not rows:
        print(f"❌ No customer found for {'id='+str(cid) if cid else 'name='+name}")
        sys.exit(1)
    if len(rows) > 1:
        print(f"⚠  Multiple customers matched:")
        for r in rows:
            print(f"   id={r[0]}  name={r[1]}")
        print("Re-run with --id to be specific.")
        sys.exit(1)
    return rows[0]

def cleanup(customer_id, customer_name, dry_run):
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning customer: {customer_name} (id={customer_id})\n")

    total = 0
    for table, fk_col, parent_table, parent_pk in CHILD_TABLES:
        if parent_table:
            # e.g. customer_task_resolutions — join through parent
            cur.execute(
                f"SELECT COUNT(*) FROM dna_app.{table} t "
                f"JOIN dna_app.{parent_table} p ON t.{fk_col} = p.{parent_pk} "
                f"WHERE p.customer_id = %s",
                (customer_id,)
            )
            count = cur.fetchone()[0]
            if count and not dry_run:
                cur.execute(
                    f"DELETE FROM dna_app.{table} t USING dna_app.{parent_table} p "
                    f"WHERE t.{fk_col} = p.{parent_pk} AND p.customer_id = %s",
                    (customer_id,)
                )
        else:
            cur.execute(f"SELECT COUNT(*) FROM dna_app.{table} WHERE {fk_col} = %s", (customer_id,))
            count = cur.fetchone()[0]
            if count and not dry_run:
                cur.execute(f"DELETE FROM dna_app.{table} WHERE {fk_col} = %s", (customer_id,))

        if count:
            print(f"  {'would delete' if dry_run else 'deleted':15s} {count:4d} row(s)  ->  {table}")
            total += count

    # Delete customer row itself
    cur.execute("SELECT COUNT(*) FROM dna_app.customers WHERE id = %s", (customer_id,))
    count = cur.fetchone()[0]
    if count:
        print(f"  {'would delete' if dry_run else 'deleted':15s} {count:4d} row(s)  ->  customers")
        total += count
        if not dry_run:
            cur.execute("DELETE FROM dna_app.customers WHERE id = %s", (customer_id,))

    if dry_run:
        conn.rollback()
        print(f"\n[DRY RUN] Would delete {total} total rows. Nothing changed.")
    else:
        conn.commit()
        print(f"\nDone. {total} total rows deleted.")
        _verify_clean(customer_id, customer_name)

    cur.close()
    conn.close()


def _verify_clean(customer_id, customer_name):
    print(f"\n[Verify] Confirming all data removed for customer id={customer_id}...")
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    all_clean = True

    tables_to_check = [
        ("customers",                 "id",          None,             None),
        ("customer_iso_plans",        "customer_id",  None,             None),
        ("customer_iso_plan_templates","plan_id",     "customer_iso_plans", "id"),
        ("customer_documents",        "customer_id",  None,             None),
        ("customer_placeholders",     "customer_id",  None,             None),
        ("customer_profile_data",     "customer_id",  None,             None),
        ("customer_tasks",            "customer_id",  None,             None),
        ("customer_task_resolutions", "task_id",      "customer_tasks", "id"),
        ("customer_configuration",    "customer_id",  None,             None),
        ("customer_collection_channels","customer_id",None,             None),
    ]

    for table, fk_col, parent_table, parent_pk in tables_to_check:
        if parent_table:
            cur.execute(
                f"SELECT COUNT(*) FROM dna_app.{table} t "
                f"JOIN dna_app.{parent_table} p ON t.{fk_col} = p.{parent_pk} "
                f"WHERE p.customer_id = %s",
                (customer_id,)
            )
        else:
            cur.execute(f"SELECT COUNT(*) FROM dna_app.{table} WHERE {fk_col} = %s", (customer_id,))
        count = cur.fetchone()[0]
        status = "CLEAN" if count == 0 else f"FAIL ({count} rows remain)"
        print(f"  {status:25s}  {table}")
        if count > 0:
            all_clean = False

    cur.close()
    conn.close()
    print(f"\n{'ALL CLEAN - customer fully removed' if all_clean else 'WARNING: some data remains'}")
    if not all_clean:
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Customer name (case-insensitive)")
    parser.add_argument("--id",   type=int, help="Customer ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()

    if not args.name and not args.id:
        print("Usage: python cleanup_customer.py --name 'Acme' OR --id 42")
        sys.exit(1)

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    customer_id, customer_name = resolve_customer(cur, name=args.name, cid=args.id)
    cur.close()
    conn.close()

    cleanup(customer_id, customer_name, dry_run=args.dry_run)
