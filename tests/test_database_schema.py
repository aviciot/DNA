"""
Test Database Schema - Milestone 1.2
Tests for ai_tasks, llm_providers, and template_reviews tables
"""
import pytest
import asyncio
from datetime import datetime, timedelta
import sys
import os
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard.backend.app.database import get_db_pool, close_db_pool
from dashboard.backend.app.config import settings


@pytest.fixture
async def db_pool():
    """Create database connection pool for testing"""
    pool = await get_db_pool()
    yield pool
    # Cleanup test data after all tests
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM dna_app.template_reviews WHERE id::text LIKE 'test-%'")
        await conn.execute("DELETE FROM dna_app.ai_tasks WHERE id::text LIKE 'test-%'")
        await conn.execute("DELETE FROM dna_app.llm_providers WHERE name LIKE 'test-%'")
    await close_db_pool()


class TestLLMProvidersTable:
    """Test llm_providers table operations"""
    
    @pytest.mark.asyncio
    async def test_query_default_providers(self, db_pool):
        """Test querying seeded LLM providers"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, display_name, enabled FROM dna_app.llm_providers ORDER BY name"
            )
            
            assert len(rows) >= 3, "Should have at least 3 seeded providers"
            
            # Check Claude exists and is enabled
            claude = next((r for r in rows if r['name'] == 'claude'), None)
            assert claude is not None, "Claude provider should exist"
            assert claude['enabled'] is True, "Claude should be enabled"
    
    @pytest.mark.asyncio
    async def test_get_default_parser(self, db_pool):
        """Test getting default parser provider"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT name, model FROM dna_app.llm_providers 
                   WHERE is_default_parser = true AND enabled = true"""
            )
            
            assert row is not None, "Should have a default parser"
            assert row['name'] == 'claude', "Claude should be default parser"
    
    @pytest.mark.asyncio
    async def test_insert_custom_provider(self, db_pool):
        """Test inserting a custom LLM provider"""
        test_id = str(uuid.uuid4()).replace('-', '')[:8]
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO dna_app.llm_providers 
                   (name, display_name, model, api_key_env, enabled) 
                   VALUES ($1, $2, $3, $4, $5)""",
                f'test-provider-{test_id}',
                'Test Provider',
                'test-model-v1',
                'TEST_API_KEY',
                False
            )
            
            # Verify insertion
            row = await conn.fetchrow(
                "SELECT * FROM dna_app.llm_providers WHERE name = $1",
                f'test-provider-{test_id}'
            )
            
            assert row is not None, "Provider should be inserted"
            assert row['display_name'] == 'Test Provider'
            assert row['enabled'] is False
    
    @pytest.mark.asyncio
    async def test_provider_costs(self, db_pool):
        """Test provider cost tracking"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT cost_per_1k_input, cost_per_1k_output 
                   FROM dna_app.llm_providers 
                   WHERE name = 'claude'"""
            )
            
            assert row is not None, "Claude provider should exist"
            assert row['cost_per_1k_input'] is not None, "Should have input cost"
            assert row['cost_per_1k_output'] is not None, "Should have output cost"
            assert float(row['cost_per_1k_input']) > 0, "Input cost should be positive"


class TestAITasksTable:
    """Test ai_tasks table operations"""
    
    @pytest.mark.asyncio
    async def test_create_task(self, db_pool):
        """Test creating an AI task"""
        task_id = f"test-{uuid.uuid4()}"
        
        async with db_pool.acquire() as conn:
            # Get default LLM provider
            provider = await conn.fetchrow(
                "SELECT id FROM dna_app.llm_providers WHERE name = 'claude'"
            )
            
            # Create task
            await conn.execute(
                """INSERT INTO dna_app.ai_tasks 
                   (id, task_type, status, llm_provider_id, llm_provider, llm_model) 
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                task_id,
                'template_parse',
                'pending',
                provider['id'],
                'claude',
                'claude-sonnet-4-5-20250929'
            )
            
            # Verify task created
            row = await conn.fetchrow(
                "SELECT * FROM dna_app.ai_tasks WHERE id = $1",
                task_id
            )
            
            assert row is not None, "Task should be created"
            assert row['task_type'] == 'template_parse'
            assert row['status'] == 'pending'
            assert row['progress'] == 0, "Initial progress should be 0"
    
    @pytest.mark.asyncio
    async def test_update_task_progress(self, db_pool):
        """Test updating task progress"""
        task_id = f"test-{uuid.uuid4()}"
        
        async with db_pool.acquire() as conn:
            # Create task
            await conn.execute(
                """INSERT INTO dna_app.ai_tasks (id, task_type, status) 
                   VALUES ($1, $2, $3)""",
                task_id, 'template_parse', 'pending'
            )
            
            # Update progress
            await conn.execute(
                """UPDATE dna_app.ai_tasks 
                   SET status = $1, progress = $2, current_step = $3, started_at = NOW()
                   WHERE id = $4""",
                'processing', 45, 'Parsing section 3 of 5', task_id
            )
            
            # Verify update
            row = await conn.fetchrow(
                "SELECT status, progress, current_step FROM dna_app.ai_tasks WHERE id = $1",
                task_id
            )
            
            assert row['status'] == 'processing'
            assert row['progress'] == 45
            assert row['current_step'] == 'Parsing section 3 of 5'
    
    @pytest.mark.asyncio
    async def test_complete_task(self, db_pool):
        """Test completing a task with results"""
        task_id = f"test-{uuid.uuid4()}"
        
        async with db_pool.acquire() as conn:
            # Create task
            await conn.execute(
                """INSERT INTO dna_app.ai_tasks (id, task_type, status, started_at) 
                   VALUES ($1, $2, $3, NOW())""",
                task_id, 'template_parse', 'processing'
            )
            
            # Complete task
            result_data = {
                'template_name': 'ISO 9001:2015',
                'sections_parsed': 12,
                'confidence': 0.95
            }
            
            await conn.execute(
                """UPDATE dna_app.ai_tasks 
                   SET status = $1, progress = $2, result = $3, 
                       completed_at = NOW(), tokens_input = $4, tokens_output = $5,
                       cost_usd = $6, duration_seconds = $7
                   WHERE id = $8""",
                'completed', 100, result_data, 1500, 800, 0.0234, 45, task_id
            )
            
            # Verify completion
            row = await conn.fetchrow(
                "SELECT * FROM dna_app.ai_tasks WHERE id = $1",
                task_id
            )
            
            assert row['status'] == 'completed'
            assert row['progress'] == 100
            assert row['result'] is not None
            assert row['tokens_input'] == 1500
            assert row['tokens_output'] == 800
            assert float(row['cost_usd']) == 0.0234
            assert row['completed_at'] is not None
    
    @pytest.mark.asyncio
    async def test_fail_task(self, db_pool):
        """Test marking task as failed with error"""
        task_id = f"test-{uuid.uuid4()}"
        
        async with db_pool.acquire() as conn:
            # Create task
            await conn.execute(
                """INSERT INTO dna_app.ai_tasks (id, task_type, status, started_at) 
                   VALUES ($1, $2, $3, NOW())""",
                task_id, 'template_parse', 'processing'
            )
            
            # Fail task
            error_message = "API rate limit exceeded"
            await conn.execute(
                """UPDATE dna_app.ai_tasks 
                   SET status = $1, error = $2, completed_at = NOW()
                   WHERE id = $3""",
                'failed', error_message, task_id
            )
            
            # Verify failure
            row = await conn.fetchrow(
                "SELECT status, error FROM dna_app.ai_tasks WHERE id = $1",
                task_id
            )
            
            assert row['status'] == 'failed'
            assert row['error'] == error_message
    
    @pytest.mark.asyncio
    async def test_task_type_constraint(self, db_pool):
        """Test task_type constraint validation"""
        task_id = f"test-{uuid.uuid4()}"
        
        async with db_pool.acquire() as conn:
            # Try invalid task type
            with pytest.raises(Exception):
                await conn.execute(
                    """INSERT INTO dna_app.ai_tasks (id, task_type, status) 
                       VALUES ($1, $2, $3)""",
                    task_id, 'invalid_type', 'pending'
                )
    
    @pytest.mark.asyncio
    async def test_progress_range_constraint(self, db_pool):
        """Test progress must be 0-100"""
        task_id = f"test-{uuid.uuid4()}"
        
        async with db_pool.acquire() as conn:
            # Create task
            await conn.execute(
                """INSERT INTO dna_app.ai_tasks (id, task_type, status) 
                   VALUES ($1, $2, $3)""",
                task_id, 'template_parse', 'pending'
            )
            
            # Try invalid progress value
            with pytest.raises(Exception):
                await conn.execute(
                    "UPDATE dna_app.ai_tasks SET progress = $1 WHERE id = $2",
                    150, task_id
                )
    
    @pytest.mark.asyncio
    async def test_query_tasks_by_status(self, db_pool):
        """Test querying tasks by status"""
        async with db_pool.acquire() as conn:
            # Create multiple test tasks
            for i in range(3):
                await conn.execute(
                    """INSERT INTO dna_app.ai_tasks (id, task_type, status) 
                       VALUES ($1, $2, $3)""",
                    f"test-query-{i}", 'template_parse', 'pending'
                )
            
            # Query pending tasks
            rows = await conn.fetch(
                """SELECT id FROM dna_app.ai_tasks 
                   WHERE status = 'pending' AND id::text LIKE 'test-query-%'"""
            )
            
            assert len(rows) >= 3, "Should find at least 3 pending test tasks"


class TestTemplateReviewsTable:
    """Test template_reviews table operations"""
    
    @pytest.mark.asyncio
    async def test_create_review(self, db_pool):
        """Test creating a template review"""
        review_id = f"test-{uuid.uuid4()}"
        task_id = f"test-{uuid.uuid4()}"
        template_id = str(uuid.uuid4())
        
        async with db_pool.acquire() as conn:
            # Create task first
            await conn.execute(
                """INSERT INTO dna_app.ai_tasks (id, task_type, status) 
                   VALUES ($1, $2, $3)""",
                task_id, 'template_review', 'completed'
            )
            
            # Create review
            await conn.execute(
                """INSERT INTO dna_app.template_reviews 
                   (id, template_id, task_id, reviewer_llm, 
                    overall_score, completeness_score, compliance_score) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                review_id, template_id, task_id, 'claude', 85, 90, 80
            )
            
            # Verify review
            row = await conn.fetchrow(
                "SELECT * FROM dna_app.template_reviews WHERE id = $1",
                review_id
            )
            
            assert row is not None, "Review should be created"
            assert row['overall_score'] == 85
            assert row['completeness_score'] == 90
            assert row['compliance_score'] == 80
    
    @pytest.mark.asyncio
    async def test_review_with_feedback(self, db_pool):
        """Test review with detailed feedback"""
        review_id = f"test-{uuid.uuid4()}"
        task_id = f"test-{uuid.uuid4()}"
        template_id = str(uuid.uuid4())
        
        async with db_pool.acquire() as conn:
            # Create task
            await conn.execute(
                "INSERT INTO dna_app.ai_tasks (id, task_type, status) VALUES ($1, $2, $3)",
                task_id, 'template_review', 'completed'
            )
            
            # Create review with feedback
            missing_fields = ['scope_description', 'quality_objectives']
            suggestions = [
                {'field': 'quality_policy', 'suggestion': 'Add more specific metrics'},
                {'field': 'process_approach', 'suggestion': 'Include flowchart'}
            ]
            compliance_issues = [
                {'section': '4.1', 'issue': 'Context not fully defined', 'severity': 'medium'}
            ]
            
            await conn.execute(
                """INSERT INTO dna_app.template_reviews 
                   (id, template_id, task_id, reviewer_llm, overall_score,
                    missing_fields, suggestions, compliance_issues, review_notes) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                review_id, template_id, task_id, 'openai', 75,
                missing_fields, suggestions, compliance_issues,
                'Good template but needs more detail in key sections'
            )
            
            # Verify feedback stored correctly
            row = await conn.fetchrow(
                "SELECT missing_fields, suggestions, compliance_issues FROM dna_app.template_reviews WHERE id = $1",
                review_id
            )
            
            assert row is not None
            assert len(row['missing_fields']) == 2
            assert len(row['suggestions']) == 2
            assert len(row['compliance_issues']) == 1
    
    @pytest.mark.asyncio
    async def test_score_constraints(self, db_pool):
        """Test score range constraints (0-100)"""
        review_id = f"test-{uuid.uuid4()}"
        task_id = f"test-{uuid.uuid4()}"
        template_id = str(uuid.uuid4())
        
        async with db_pool.acquire() as conn:
            # Create task
            await conn.execute(
                "INSERT INTO dna_app.ai_tasks (id, task_type, status) VALUES ($1, $2, $3)",
                task_id, 'template_review', 'completed'
            )
            
            # Try invalid score
            with pytest.raises(Exception):
                await conn.execute(
                    """INSERT INTO dna_app.template_reviews 
                       (id, template_id, task_id, reviewer_llm, overall_score) 
                       VALUES ($1, $2, $3, $4, $5)""",
                    review_id, template_id, task_id, 'claude', 150
                )


class TestDatabaseIndexes:
    """Test database indexes exist and are used"""
    
    @pytest.mark.asyncio
    async def test_ai_tasks_indexes_exist(self, db_pool):
        """Test ai_tasks table has required indexes"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT indexname FROM pg_indexes 
                   WHERE tablename = 'ai_tasks' AND schemaname = 'dna_app'
                   ORDER BY indexname"""
            )
            
            index_names = [row['indexname'] for row in rows]
            
            assert 'idx_ai_tasks_status' in index_names
            assert 'idx_ai_tasks_type' in index_names
            assert 'idx_ai_tasks_related' in index_names
            assert 'idx_ai_tasks_created_by' in index_names
    
    @pytest.mark.asyncio
    async def test_llm_providers_indexes_exist(self, db_pool):
        """Test llm_providers table has required indexes"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT indexname FROM pg_indexes 
                   WHERE tablename = 'llm_providers' AND schemaname = 'dna_app'
                   ORDER BY indexname"""
            )
            
            index_names = [row['indexname'] for row in rows]
            
            assert 'idx_llm_providers_name' in index_names
            assert 'idx_llm_providers_enabled' in index_names


# Run tests with: pytest tests/test_database_schema.py -v
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
