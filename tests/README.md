# DNA Test Suite

Comprehensive test suite for DNA ISO Certification Dashboard - testing Redis integration, database schema, and API functionality.

## Test Structure

```
tests/
├── __init__.py                    # Package initialization
├── conftest.py                    # Shared pytest fixtures
├── test_redis_integration.py     # Redis Streams & Pub/Sub tests (Milestone 1.1)
├── test_database_schema.py       # Database schema tests (Milestone 1.2)
└── README.md                      # This file
```

## Prerequisites

### 1. Install Test Dependencies

```bash
pip install pytest pytest-asyncio
```

### 2. Start Required Services

Make sure Docker services are running:

```bash
docker-compose up -d
```

Verify services are healthy:
```bash
docker-compose ps
```

All services should show "healthy" status:
- dna-postgres (port 5432)
- dna-redis (port 6379)
- dna-backend (port 8400)

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
# Redis integration tests
pytest tests/test_redis_integration.py -v

# Database schema tests
pytest tests/test_database_schema.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_redis_integration.py::TestRedisConnection -v
```

### Run Specific Test Function
```bash
pytest tests/test_redis_integration.py::TestRedisConnection::test_connection_success -v
```

### Run Tests by Marker
```bash
# Run only integration tests
pytest -m integration -v

# Run only Redis tests
pytest -m redis -v

# Skip slow tests
pytest -m "not slow" -v
```

## Test Coverage

### Milestone 1.1: Redis Integration

**test_redis_integration.py** (9 test classes, 15+ tests)

- TestRedisConnection
  - Connection and ping
  - Server info retrieval
  
- TestRedisStreams
  - Adding messages to streams
  - Reading messages from streams
  - Consumer group creation
  - Stream length tracking
  - Max length enforcement
  
- TestRedisPubSub
  - Publishing messages
  - Subscribing to channels
  - Receiving messages
  
- TestRedisDataTypes
  - JSON serialization
  - Special character handling
  
- TestRedisErrorHandling
  - Disconnect and reconnect
  - Invalid operations

### Milestone 1.2: Database Schema

**test_database_schema.py** (4 test classes, 20+ tests)

- TestLLMProvidersTable
  - Query seeded providers
  - Get default parser
  - Insert custom provider
  - Cost tracking
  
- TestAITasksTable
  - Create task
  - Update progress
  - Complete task with results
  - Fail task with error
  - Task type constraint validation
  - Progress range validation
  - Query tasks by status
  
- TestTemplateReviewsTable
  - Create review
  - Store detailed feedback (missing fields, suggestions, compliance issues)
  - Score constraint validation
  
- TestDatabaseIndexes
  - Verify required indexes exist
  - Check index naming conventions

## Test Output

### Successful Test Run
```
tests/test_redis_integration.py::TestRedisConnection::test_connection_success PASSED
tests/test_redis_integration.py::TestRedisStreams::test_add_to_stream PASSED
tests/test_database_schema.py::TestAITasksTable::test_create_task PASSED

========================= 35 passed in 12.45s =========================
```

### Failed Test Example
```
tests/test_redis_integration.py::TestRedisConnection::test_connection_success FAILED

E   AssertionError: Redis ping should return True
E   assert False is True

========================= 1 failed, 34 passed in 12.45s =================
```

## Troubleshooting

### Redis Connection Errors
```
Error: ConnectionError: Error connecting to Redis
```
**Solution:** Ensure Redis is running:
```bash
docker-compose ps dna-redis
docker-compose logs dna-redis
```

### Database Connection Errors
```
Error: asyncpg.exceptions.InvalidCatalogNameError: database "dna" does not exist
```
**Solution:** Ensure PostgreSQL is initialized:
```bash
docker-compose logs dna-postgres
docker-compose restart dna-postgres
```

### Import Errors
```
ModuleNotFoundError: No module named 'dashboard'
```
**Solution:** Run tests from project root:
```bash
cd DNA
pytest tests/ -v
```

### Test Cleanup Issues

Tests automatically clean up test data (entries with 'test-' prefix). If cleanup fails:

```bash
# Manual cleanup SQL
docker exec -i dna-postgres psql -U dna_user -d dna -c "
DELETE FROM dna_app.template_reviews WHERE id::text LIKE 'test-%';
DELETE FROM dna_app.ai_tasks WHERE id::text LIKE 'test-%';
DELETE FROM dna_app.llm_providers WHERE name LIKE 'test-%';
"
```

## Writing New Tests

### Test Template
```python
import pytest

class TestMyFeature:
    @pytest.mark.asyncio
    async def test_my_functionality(self, db_pool):
        # Arrange
        test_data = {'key': 'value'}
        
        # Act
        result = await some_function(test_data)
        
        # Assert
        assert result is not None
        assert result['key'] == 'expected'
```

### Best Practices

1. **Use descriptive test names**: `test_create_task_with_valid_data`
2. **Clean up test data**: Use 'test-' prefix for IDs
3. **Test edge cases**: Invalid inputs, constraints, boundaries
4. **Use fixtures**: Share common setup via conftest.py
5. **Mark tests appropriately**: @pytest.mark.asyncio, @pytest.mark.slow
6. **No unicode in test files**: ASCII only for compatibility

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Tests
  run: |
    docker-compose up -d
    sleep 10  # Wait for services
    pytest tests/ -v --junit-xml=test-results.xml
```

### Pre-commit Hook
```bash
#!/bin/bash
pytest tests/ -v || exit 1
```

## Next Steps

After Milestone 1.3 (Task Management API):
- Add `test_task_api.py` for endpoint testing
- Test task creation, status updates, cancellation

After Milestone 1.4 (Progress WebSocket):
- Add `test_websocket_progress.py` for WebSocket testing
- Test real-time progress updates

## Documentation

- Architecture: See ARCHITECTURE.md
- Implementation Progress: See IMPLEMENTATION_PROGRESS.md
- Service Configuration: See rules.md
