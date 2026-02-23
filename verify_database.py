#!/usr/bin/env python
"""
Quick database verification script
===================================
Checks that new database structure is in place.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def verify_database():
    """Verify database structure."""
    print("[*] Verifying database structure...")
    print()

    # Connect to database
    conn = await asyncpg.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 5432)),
        database=os.getenv("DATABASE_NAME", "dna"),
        user=os.getenv("DATABASE_USER", "dna_user"),
        password=os.getenv("DATABASE_PASSWORD", "dna_password_dev"),
    )

    try:
        # Test 1: Templates table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'templates'
            )
        """)
        print(f"[OK] templates table exists: {exists}")

        # Test 2: Old catalog_templates removed
        old_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'catalog_templates'
            )
        """)
        print(f"[OK] catalog_templates removed: {not old_exists}")

        # Test 3: customer_responses exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'customer_responses'
            )
        """)
        print(f"[OK] customer_responses table exists: {exists}")

        # Test 4: generated_documents exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'generated_documents'
            )
        """)
        print(f"[OK] generated_documents table exists: {exists}")

        # Test 5: View exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.views
                WHERE table_schema = 'dna_app'
                AND table_name = 'v_templates_with_details'
            )
        """)
        print(f"[OK] v_templates_with_details view exists: {exists}")

        # Test 6: Check templates table structure
        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'dna_app'
            AND table_name = 'templates'
            ORDER BY ordinal_position
        """)
        column_names = [row['column_name'] for row in columns]

        required_columns = [
            'id', 'name', 'template_structure',
            'total_fixed_sections', 'total_fillable_sections',
            'semantic_tags', 'iso_standard'
        ]

        all_present = all(col in column_names for col in required_columns)
        print(f"[OK] templates table has all required columns: {all_present}")
        if not all_present:
            missing = [col for col in required_columns if col not in column_names]
            print(f"     Missing: {missing}")

        # Test 7: Check if any templates exist yet
        count = await conn.fetchval("SELECT COUNT(*) FROM dna_app.templates")
        print(f"[INFO] Templates in database: {count}")

        print()
        print("[SUCCESS] Database structure verification complete!")
        print()
        print("[NEXT] Ready to test:")
        print("   1. Upload ISMS document via web UI")
        print("   2. Click 'Generate Template'")
        print("   3. Watch AI parse with new approach")
        print()

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(verify_database())
