import asyncio
import asyncpg
import os

async def main():
    # Try different connection strings
    connection_strings = [
        'postgresql://dna_user:dna_password_dev@localhost:5432/dna',
        'postgresql://postgres:postgres@localhost:5432/dna',
        'postgresql://dna_user:dna_password_dev@dna-postgres:5432/dna',
    ]

    conn = None
    for conn_str in connection_strings:
        try:
            print(f"Trying: {conn_str.split('@')[1]}...")
            conn = await asyncpg.connect(conn_str)
            print(f"[OK] Connected successfully!")
            break
        except Exception as e:
            print(f"[FAIL] {str(e)[:50]}")
            continue

    if not conn:
        print("\n[ERROR] Could not connect to database with any credentials")
        return

    print("="*60)
    print("CURRENT DATABASE STATE - Customer ID: 4")
    print("="*60)

    # Check plans
    plans = await conn.fetch("""
        SELECT id, customer_id, iso_standard_id, is_ignored, plan_status, created_at
        FROM dna_app.customer_iso_plans
        WHERE customer_id = 4
        ORDER BY created_at DESC
    """)

    print(f"\nPLANS: {len(plans)} total")
    for p in plans:
        print(f"  - Plan ID: {p['id']}")
        print(f"    Status: {p['plan_status']} | Ignored: {p['is_ignored']}")
        print(f"    Created: {p['created_at']}")

    # Check templates
    templates = await conn.fetch("""
        SELECT cipt.plan_id, cipt.template_id, cipt.is_ignored
        FROM dna_app.customer_iso_plan_templates cipt
        JOIN dna_app.customer_iso_plans cip ON cipt.plan_id = cip.id
        WHERE cip.customer_id = 4
    """)

    print(f"\nTEMPLATE ASSIGNMENTS: {len(templates)} total")
    for t in templates:
        print(f"  - Plan: {t['plan_id']} | Template: {t['template_id']} | Ignored: {t['is_ignored']}")

    # Check tasks
    tasks = await conn.fetch("""
        SELECT id, plan_id, status, is_ignored
        FROM dna_app.customer_tasks
        WHERE customer_id = 4
        ORDER BY created_at DESC
    """)

    print(f"\nTASKS: {len(tasks)} total")
    task_summary = {}
    for t in tasks:
        key = f"{t['status']} (ignored={t['is_ignored']})"
        task_summary[key] = task_summary.get(key, 0) + 1

    for status, count in task_summary.items():
        print(f"  - {status}: {count} tasks")

    # Cleanup
    print("\n" + "="*60)
    print("PERFORMING CLEANUP")
    print("="*60)

    # Delete all plans for customer 4
    deleted_plans = await conn.execute("""
        DELETE FROM dna_app.customer_iso_plans
        WHERE customer_id = 4
    """)
    print(f"\n[OK] Deleted plans: {deleted_plans}")

    # Delete all tasks for customer 4
    deleted_tasks = await conn.execute("""
        DELETE FROM dna_app.customer_tasks
        WHERE customer_id = 4
    """)
    print(f"[OK] Deleted tasks: {deleted_tasks}")

    print("\n" + "="*60)
    print("CLEANUP COMPLETE - Database is clean!")
    print("="*60)

    await conn.close()

asyncio.run(main())
