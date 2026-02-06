"""
Shared pytest fixtures and configuration
"""
import pytest
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    return {
        'database_host': os.getenv('DATABASE_HOST', 'localhost'),
        'database_port': int(os.getenv('DATABASE_PORT', '5432')),
        'database_name': os.getenv('DATABASE_NAME', 'dna'),
        'database_user': os.getenv('DATABASE_USER', 'dna_user'),
        'redis_host': os.getenv('REDIS_HOST', 'localhost'),
        'redis_port': int(os.getenv('REDIS_PORT', '6379')),
    }


def pytest_configure(config):
    """Configure pytest with custom settings"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers"""
    for item in items:
        # Add asyncio marker to all async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
        
        # Add integration marker to tests requiring external services
        if 'redis' in item.nodeid or 'database' in item.nodeid:
            item.add_marker(pytest.mark.integration)
