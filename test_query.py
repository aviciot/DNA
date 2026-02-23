import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://dna_user:dna_password_dev@localhost:5432/dna')

    # Get the ISO ID first
    iso_id = await conn.fetchval("""
        SELECT id FROM dna_app.iso_standards
        WHERE code = 'ISO 27001:2022'
        LIMIT 1
    """)

    print(f"ISO Standard ID: {iso_id}")

    # Test the exact query from the code
    existing_active_plan = await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM dna_app.customer_iso_plans
            WHERE customer_id = $1
              AND iso_standard_id = $2
              AND (is_ignored = false OR is_ignored IS NULL)
        )
    """, 4, iso_id)

    print(f"\nQuery result (existing_active_plan): {existing_active_plan}")

    # Also check what plans exist
    plans = await conn.fetch("""
        SELECT id, is_ignored, plan_status
        FROM dna_app.customer_iso_plans
        WHERE customer_id = $1 AND iso_standard_id = $2
    """, 4, iso_id)

    print(f"\nPlans found: {len(plans)}")
    for p in plans:
        print(f"  - id={p['id']}")
        print(f"    is_ignored={p['is_ignored']}")
        print(f"    plan_status={p['plan_status']}")
        print(f"    Matches (is_ignored=false OR is_ignored IS NULL)? {p['is_ignored'] is False or p['is_ignored'] is None}")

    await conn.close()

asyncio.run(main())
