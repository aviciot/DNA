"""
Test new database structure - Fixed vs Fillable sections
=========================================================
"""

import pytest
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="module")
async def db_pool():
    """Create database connection pool."""
    pool = await asyncpg.create_pool(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 5432)),
        database=os.getenv("DATABASE_NAME", "dna"),
        user=os.getenv("DATABASE_USER", "dna_user"),
        password=os.getenv("DATABASE_PASSWORD", "dna_password_dev"),
    )
    yield pool
    await pool.close()


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_templates_table_exists(db_pool):
    """Test that templates table exists."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'templates'
            )
        """)
        assert exists, "templates table should exist"


@pytest.mark.asyncio
async def test_templates_table_structure(db_pool):
    """Test that templates table has correct columns."""
    async with db_pool.acquire() as conn:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'dna_app'
            AND table_name = 'templates'
            ORDER BY ordinal_position
        """)

        column_names = [row['column_name'] for row in columns]

        # Check required columns exist
        assert 'id' in column_names
        assert 'name' in column_names
        assert 'template_structure' in column_names
        assert 'total_fixed_sections' in column_names
        assert 'total_fillable_sections' in column_names
        assert 'semantic_tags' in column_names
        assert 'iso_standard' in column_names


@pytest.mark.asyncio
async def test_customer_responses_table_exists(db_pool):
    """Test that customer_responses table exists."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'customer_responses'
            )
        """)
        assert exists, "customer_responses table should exist"


@pytest.mark.asyncio
async def test_generated_documents_table_exists(db_pool):
    """Test that generated_documents table exists."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'generated_documents'
            )
        """)
        assert exists, "generated_documents table should exist"


@pytest.mark.asyncio
async def test_old_catalog_templates_removed(db_pool):
    """Test that old catalog_templates table was removed."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'dna_app'
                AND table_name = 'catalog_templates'
            )
        """)
        assert not exists, "catalog_templates table should be removed"


@pytest.mark.asyncio
async def test_view_templates_with_details_exists(db_pool):
    """Test that v_templates_with_details view exists."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.views
                WHERE table_schema = 'dna_app'
                AND table_name = 'v_templates_with_details'
            )
        """)
        assert exists, "v_templates_with_details view should exist"


@pytest.mark.asyncio
async def test_update_template_stats_function_exists(db_pool):
    """Test that update_template_stats function exists."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_proc
                WHERE proname = 'update_template_stats'
            )
        """)
        assert exists, "update_template_stats function should exist"


@pytest.mark.asyncio
async def test_template_structure_jsonb_format(db_pool):
    """Test that template_structure column is JSONB."""
    async with db_pool.acquire() as conn:
        data_type = await conn.fetchval("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'dna_app'
            AND table_name = 'templates'
            AND column_name = 'template_structure'
        """)
        assert data_type == 'jsonb', "template_structure should be JSONB type"


@pytest.mark.asyncio
async def test_semantic_tags_array_format(db_pool):
    """Test that semantic_tags column is TEXT[]."""
    async with db_pool.acquire() as conn:
        data_type = await conn.fetchval("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'dna_app'
            AND table_name = 'templates'
            AND column_name = 'semantic_tags'
        """)
        assert data_type == 'ARRAY', "semantic_tags should be ARRAY type"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
