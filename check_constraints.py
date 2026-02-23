import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://dna_user:dna_password_dev@localhost:5432/dna')

    # Check unique constraints on customer_iso_plans table
    constraints = await conn.fetch("""
        SELECT conname, contype, pg_get_constraintdef(c.oid) as definition
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        JOIN pg_class cl ON cl.oid = c.conrelid
        WHERE cl.relname = 'customer_iso_plans'
          AND n.nspname = 'dna_app'
          AND contype IN ('u', 'p')
    """)

    print("="*60)
    print("UNIQUE CONSTRAINTS on customer_iso_plans")
    print("="*60)
    for c in constraints:
        print(f"\nName: {c['conname']}")
        print(f"Type: {c['contype']}")
        print(f"Definition: {c['definition']}")

    await conn.close()

asyncio.run(main())
