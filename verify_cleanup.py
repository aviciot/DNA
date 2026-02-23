import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://dna_user:dna_password_dev@localhost:5432/dna')

    plans = await conn.fetchval('SELECT COUNT(*) FROM dna_app.customer_iso_plans WHERE customer_id = 4')
    tasks = await conn.fetchval('SELECT COUNT(*) FROM dna_app.customer_tasks WHERE customer_id = 4')
    templates = await conn.fetchval('''
        SELECT COUNT(*) FROM dna_app.customer_iso_plan_templates cipt
        JOIN dna_app.customer_iso_plans cip ON cipt.plan_id = cip.id
        WHERE cip.customer_id = 4
    ''')

    print("="*50)
    print("DATABASE VERIFICATION - Customer ID: 4")
    print("="*50)
    print(f"Plans: {plans}")
    print(f"Tasks: {tasks}")
    print(f"Templates: {templates}")
    print("="*50)

    if plans == 0 and tasks == 0 and templates == 0:
        print("[OK] Database is clean!")
    else:
        print("[WARNING] Database still has data")

    await conn.close()

asyncio.run(main())
