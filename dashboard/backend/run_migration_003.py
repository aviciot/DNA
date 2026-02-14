"""
Run Migration 003: Add template_id to customer_tasks
"""

import asyncio
import asyncpg
import os
from pathlib import Path

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "dna_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


async def run_migration():
    """Run the migration script."""
    migration_file = Path(__file__).parent / "migrations" / "003_add_template_id_to_tasks.sql"

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print(f"[*] Reading migration file: {migration_file}")
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    print(f"[*] Connecting to database: {DB_NAME} at {DB_HOST}:{DB_PORT}")

    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        print("[+] Connected to database")
        print("[*] Running migration...")

        # Execute migration
        await conn.execute(migration_sql)

        # Check results
        task_count = await conn.fetchval(
            "SELECT COUNT(*) FROM dna_app.customer_tasks WHERE template_id IS NOT NULL"
        )

        total_tasks = await conn.fetchval(
            "SELECT COUNT(*) FROM dna_app.customer_tasks"
        )

        print(f"\n[+] Migration 003 completed successfully!")
        print(f"[*] Results:")
        print(f"   - Total tasks: {total_tasks}")
        print(f"   - Tasks with template_id: {task_count}")
        print(f"   - Tasks backfilled: {task_count}/{total_tasks}")

        await conn.close()
        return True

    except Exception as e:
        print(f"\n[-] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Migration 003: Add template_id to customer_tasks")
    print("=" * 60)

    success = asyncio.run(run_migration())

    if success:
        print("\n[+] Migration completed successfully!")
        print("[*] Next steps:")
        print("   1. Restart backend container: docker-compose restart backend")
        print("   2. Restart frontend container: docker-compose restart frontend")
        print("   3. Test customer workspace - tasks should now be grouped correctly by template")
    else:
        print("\n[-] Migration failed. Please check the errors above.")
        exit(1)
