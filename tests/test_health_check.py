"""
Simple Health Check Tests - Verify Services Are Running
Run these tests first to ensure Docker services are ready
"""
import requests
import redis
import asyncpg
import asyncio
import json


def test_redis_connection():
    """Test Redis is accessible"""
    print("\nTesting Redis connection...")
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        result = r.ping()
        assert result is True, "Redis ping failed"
        print("  [PASS] Redis connection successful")
        
        # Test basic operations
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        assert value == 'test_value', "Redis get/set failed"
        r.delete('test_key')
        print("  [PASS] Redis operations working")
        
    except Exception as e:
        print(f"  [FAIL] Redis connection error: {e}")
        raise


async def test_database_connection_async():
    """Test PostgreSQL database is accessible"""
    print("\nTesting Database connection...")
    try:
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            user='dna_user',
            password='dna_password',
            database='dna'
        )
        
        # Test query
        version = await conn.fetchval('SELECT version()')
        assert version is not None, "Database query failed"
        print(f"  [PASS] Database connection successful")
        print(f"  [INFO] PostgreSQL version: {version.split(',')[0]}")
        
        # Test tables exist
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'dna_app' 
            AND tablename IN ('ai_tasks', 'llm_providers', 'template_reviews')
            ORDER BY tablename
        """)
        
        table_names = [t['tablename'] for t in tables]
        print(f"  [PASS] Found tables: {', '.join(table_names)}")
        
        assert 'ai_tasks' in table_names, "ai_tasks table not found"
        assert 'llm_providers' in table_names, "llm_providers table not found"
        assert 'template_reviews' in table_names, "template_reviews table not found"
        
        await conn.close()
        
    except Exception as e:
        print(f"  [FAIL] Database connection error: {e}")
        raise


def test_database_connection():
    """Wrapper to run async database test"""
    asyncio.run(test_database_connection_async())


def test_backend_api():
    """Test backend API is responding"""
    print("\nTesting Backend API...")
    try:
        response = requests.get('http://localhost:8400/health', timeout=5)
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
        
        data = response.json()
        print(f"  [PASS] Backend API responding")
        print(f"  [INFO] Status: {data.get('status')}")
        print(f"  [INFO] Database: {data.get('database')}")
        print(f"  [INFO] Redis: {data.get('redis')}")
        
        assert data.get('status') == 'healthy', "Backend not healthy"
        assert data.get('database') == 'connected', "Database not connected"
        assert data.get('redis') == 'connected', "Redis not connected"
        
    except Exception as e:
        print(f"  [FAIL] Backend API error: {e}")
        raise


def test_llm_providers_seeded():
    """Test LLM providers were seeded correctly"""
    print("\nTesting LLM Providers...")
    
    async def check_providers():
        conn = await asyncpg.connect(
            host='localhost', port=5432, user='dna_user',
            password='dna_password', database='dna'
        )
        
        providers = await conn.fetch(
            "SELECT name, enabled, is_default_parser FROM dna_app.llm_providers ORDER BY name"
        )
        
        provider_dict = {p['name']: p for p in providers}
        
        # Check Claude
        assert 'claude' in provider_dict, "Claude provider not found"
        assert provider_dict['claude']['enabled'] is True, "Claude should be enabled"
        assert provider_dict['claude']['is_default_parser'] is True, "Claude should be default parser"
        print("  [PASS] Claude provider configured correctly")
        
        # Check other providers exist
        assert 'openai' in provider_dict, "OpenAI provider not found"
        assert 'gemini' in provider_dict, "Gemini provider not found"
        print("  [PASS] All providers seeded (claude, openai, gemini)")
        
        await conn.close()
    
    try:
        asyncio.run(check_providers())
    except Exception as e:
        print(f"  [FAIL] LLM providers check error: {e}")
        raise


if __name__ == '__main__':
    print("=" * 70)
    print("DNA Services Health Check")
    print("=" * 70)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Database Connection", test_database_connection),
        ("Backend API", test_backend_api),
        ("LLM Providers", test_llm_providers_seeded),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n[ERROR] {name} test failed: {e}")
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        exit(1)
    else:
        print("\n[SUCCESS] All service health checks passed!")
        exit(0)
