"""
Customer Data Cleanup Script
=============================
Deletes ALL customer data from all customer-related tables.
Master data (templates, iso_standards, etc.) is NOT touched.

Run: python cleanup_customer_data.py
"""

import asyncio
import asyncpg
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "dna_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SCHEMA = "dna_app"

# Order matters — delete children before parents
TABLES = [
    "customer_task_resolutions",
    "customer_tasks",
    "customer_placeholders",
    "customer_profile_data",
    "customer_documents",
    "customer_iso_plan_templates",
    "customer_iso_plans",
    "customer_configuration",
    "customers",
]


async def cleanup():
    print(f"Connecting to {DB_NAME} at {DB_HOST}:{DB_PORT}...")
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

    print("\nCounts before cleanup:")
    for table in TABLES:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
        print(f"  {table}: {count}")

    confirm = input("\nDelete ALL customer data? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        await conn.close()
        return

    async with conn.transaction():
        for table in TABLES:
            deleted = await conn.execute(f"DELETE FROM {SCHEMA}.{table}")
            print(f"  Cleared {table} — {deleted}")

    print("\nDone. All customer data removed. Master templates untouched.")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(cleanup())
