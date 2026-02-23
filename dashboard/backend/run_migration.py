"""
Run database migration for ISO Certification System
"""

import asyncio
import asyncpg
import sys
from pathlib import Path


async def run_migration():
    """Run the migration SQL file"""

    # Read migration file
    migration_file = Path(__file__).parent / "migrations" / "002_iso_certification_system.sql"

    if not migration_file.exists():
        print(f"Error: Migration file not found: {migration_file}")
        sys.exit(1)

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    print(f"Running migration: {migration_file.name}")
    print("=" * 80)

    # Connect to database
    try:
        conn = await asyncpg.connect(
            host='dna-postgres',
            port=5432,
            database='dna',
            user='dna_user',
            password='dna_password_dev'
        )

        print("✓ Connected to database")

        # Run migration
        await conn.execute(sql)

        print("✓ Migration completed successfully!")
        print("=" * 80)
        print("\nCreated:")
        print("  - 9 new columns in customers table")
        print("  - 7 new tables:")
        print("    • customer_iso_plans")
        print("    • customer_iso_plan_templates")
        print("    • customer_documents")
        print("    • customer_tasks")
        print("    • customer_document_history")
        print("    • customer_storage_files")
        print("    • customer_interview_sessions")
        print("  - 2 new views:")
        print("    • v_customer_iso_progress")
        print("    • v_customer_overall_progress")

        await conn.close()

    except asyncpg.PostgresError as e:
        print(f"✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migration())
