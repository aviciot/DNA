import asyncio
import asyncpg
from datetime import date

async def main():
    conn = await asyncpg.connect('postgresql://dna_user:dna_password_dev@localhost:5432/dna')

    # Get ISO ID
    iso_id = await conn.fetchval("""
        SELECT id FROM dna_app.iso_standards
        WHERE code = 'ISO 27001:2022'
        LIMIT 1
    """)

    print(f"ISO Standard ID: {iso_id}")
    print(f"Customer ID: 4")
    print("\nAttempting INSERT with ON CONFLICT...")

    try:
        async with conn.transaction():
            result = await conn.fetchrow("""
                INSERT INTO dna_app.customer_iso_plans (
                    customer_id, iso_standard_id, plan_name,
                    target_completion_date, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (customer_id, iso_standard_id)
                DO UPDATE SET
                    plan_name = EXCLUDED.plan_name,
                    target_completion_date = EXCLUDED.target_completion_date,
                    is_ignored = false,
                    ignored_at = NULL,
                    ignored_by = NULL,
                    ignore_reason = NULL,
                    plan_status = 'active',
                    created_by = EXCLUDED.created_by,
                    created_at = NOW()
                RETURNING id, customer_id, iso_standard_id
            """, 4, iso_id, "Test Plan", date(2026, 12, 31), 1)

            print(f"\n[SUCCESS] Plan ID: {result['id']}")
            print("ON CONFLICT worked - plan reactivated!")

            # Check the plan state
            plan = await conn.fetchrow("""
                SELECT is_ignored, plan_status FROM dna_app.customer_iso_plans
                WHERE id = $1
            """, result['id'])

            print(f"  is_ignored: {plan['is_ignored']}")
            print(f"  plan_status: {plan['plan_status']}")

    except asyncpg.UniqueViolationError as e:
        print(f"\n[ERROR] UniqueViolationError: {e}")
        print("ON CONFLICT did NOT work!")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")

    await conn.close()

asyncio.run(main())
