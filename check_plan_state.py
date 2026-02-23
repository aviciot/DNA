import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://dna_user:dna_password_dev@localhost:5432/dna')

    plans = await conn.fetch('''
        SELECT id, is_ignored, plan_status, created_at
        FROM dna_app.customer_iso_plans
        WHERE customer_id = 4
    ''')

    print("="*60)
    print("PLAN STATE - Customer ID: 4")
    print("="*60)
    for p in plans:
        print(f"Plan ID: {p['id']}")
        print(f"  is_ignored: {p['is_ignored']}")
        print(f"  plan_status: {p['plan_status']}")
        print(f"  created_at: {p['created_at']}")

    tasks = await conn.fetch('''
        SELECT status, is_ignored, COUNT(*) as count
        FROM dna_app.customer_tasks
        WHERE customer_id = 4
        GROUP BY status, is_ignored
    ''')

    print("\nTASKS:")
    for t in tasks:
        print(f"  status={t['status']}, is_ignored={t['is_ignored']}: {t['count']} tasks")

    await conn.close()

asyncio.run(main())
