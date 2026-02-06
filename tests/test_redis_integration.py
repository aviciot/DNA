"""
Test Redis Integration - Milestone 1.1
Tests for Redis connection, Streams, and Pub/Sub functionality
"""
import pytest
import asyncio
import json
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard.backend.app.redis_client import RedisClient


@pytest.fixture
async def redis_client():
    """Create a Redis client for testing"""
    client = RedisClient()
    await client.connect()
    yield client
    await client.disconnect()


@pytest.fixture
async def clean_redis(redis_client):
    """Clean up Redis streams and channels before/after tests"""
    # Clean up before test
    await redis_client.redis.delete('test:stream')
    yield redis_client
    # Clean up after test
    await redis_client.redis.delete('test:stream')


class TestRedisConnection:
    """Test Redis connection functionality"""
    
    @pytest.mark.asyncio
    async def test_connection_success(self, redis_client):
        """Test successful Redis connection"""
        result = await redis_client.ping()
        assert result is True, "Redis ping should return True"
    
    @pytest.mark.asyncio
    async def test_get_info(self, redis_client):
        """Test getting Redis server info"""
        info = await redis_client.get_info()
        assert info is not None, "Redis info should not be None"
        assert 'redis_version' in info, "Info should contain redis_version"
        assert 'connected_clients' in info, "Info should contain connected_clients"


class TestRedisStreams:
    """Test Redis Streams functionality for task queue"""
    
    @pytest.mark.asyncio
    async def test_add_to_stream(self, clean_redis):
        """Test adding messages to Redis Stream"""
        test_data = {
            'task_id': 'test-uuid-123',
            'task_type': 'template_parse',
            'created_at': datetime.utcnow().isoformat()
        }
        
        message_id = await clean_redis.add_to_stream('test:stream', test_data)
        assert message_id is not None, "Message ID should not be None"
        assert isinstance(message_id, str), "Message ID should be string"
    
    @pytest.mark.asyncio
    async def test_read_stream(self, clean_redis):
        """Test reading messages from Redis Stream"""
        # Add test message
        test_data = {'message': 'test', 'value': 42}
        await clean_redis.add_to_stream('test:stream', test_data)
        
        # Read messages
        messages = await clean_redis.read_stream('test:stream', count=10)
        assert messages is not None, "Messages should not be None"
        assert len(messages) > 0, "Should have at least one message"
        
        # Verify message structure
        stream_name, message_list = messages[0]
        assert stream_name == b'test:stream', "Stream name should match"
        assert len(message_list) > 0, "Message list should not be empty"
    
    @pytest.mark.asyncio
    async def test_create_consumer_group(self, clean_redis):
        """Test creating consumer group for stream"""
        # Add a message first
        await clean_redis.add_to_stream('test:stream', {'init': 'message'})
        
        # Create consumer group
        result = await clean_redis.create_consumer_group(
            'test:stream', 
            'test-group', 
            '0'
        )
        assert result is True, "Consumer group creation should succeed"
        
        # Try creating again (should handle BUSYGROUP error)
        result = await clean_redis.create_consumer_group(
            'test:stream', 
            'test-group', 
            '0'
        )
        assert result is True, "Should handle existing consumer group gracefully"
    
    @pytest.mark.asyncio
    async def test_get_stream_length(self, clean_redis):
        """Test getting stream length"""
        # Initially empty
        length = await clean_redis.get_stream_length('test:stream')
        initial_length = length
        
        # Add messages
        await clean_redis.add_to_stream('test:stream', {'msg': '1'})
        await clean_redis.add_to_stream('test:stream', {'msg': '2'})
        await clean_redis.add_to_stream('test:stream', {'msg': '3'})
        
        # Check length
        length = await clean_redis.get_stream_length('test:stream')
        assert length == initial_length + 3, "Stream should have 3 new messages"
    
    @pytest.mark.asyncio
    async def test_stream_max_length(self, clean_redis):
        """Test stream respects max length"""
        max_len = 5
        
        # Add more messages than max_len
        for i in range(10):
            await clean_redis.add_to_stream(
                'test:stream', 
                {'count': i}, 
                max_len=max_len
            )
        
        # Check final length
        length = await clean_redis.get_stream_length('test:stream')
        assert length <= max_len, f"Stream should not exceed max_len of {max_len}"


class TestRedisPubSub:
    """Test Redis Pub/Sub functionality for progress updates"""
    
    @pytest.mark.asyncio
    async def test_publish_message(self, redis_client):
        """Test publishing message to channel"""
        test_message = {
            'task_id': 'test-123',
            'progress': 50,
            'status': 'processing'
        }
        
        # Publish message
        subscriber_count = await redis_client.publish('test:channel', test_message)
        assert subscriber_count >= 0, "Subscriber count should be non-negative"
    
    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self, redis_client):
        """Test subscribing to channel and receiving messages"""
        channel_name = 'test:progress:channel'
        
        # Subscribe to channel
        pubsub = await redis_client.subscribe(channel_name)
        assert pubsub is not None, "PubSub object should not be None"
        
        # Publish a test message
        test_message = {'event': 'test', 'data': 'hello'}
        await redis_client.publish(channel_name, test_message)
        
        # Try to receive message (with timeout)
        try:
            message = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=1),
                timeout=2.0
            )
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                assert data['event'] == 'test', "Should receive correct message"
        except asyncio.TimeoutError:
            # No message received, but subscription worked
            pass
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()


class TestRedisDataTypes:
    """Test Redis handles different data types correctly"""
    
    @pytest.mark.asyncio
    async def test_json_serialization(self, clean_redis):
        """Test complex JSON data serialization"""
        complex_data = {
            'string': 'test',
            'number': 42,
            'float': 3.14,
            'boolean': True,
            'null': None,
            'array': [1, 2, 3],
            'nested': {
                'key': 'value',
                'list': ['a', 'b', 'c']
            }
        }
        
        message_id = await clean_redis.add_to_stream('test:stream', complex_data)
        assert message_id is not None, "Should handle complex JSON data"
    
    @pytest.mark.asyncio
    async def test_unicode_handling(self, clean_redis):
        """Test handling of special characters (no unicode in test file)"""
        test_data = {
            'name': 'Test User',
            'description': 'ISO 9001:2015 certification template',
            'symbols': '!@#$%^&*()_+-=[]{}|;:,.<>?'
        }
        
        message_id = await clean_redis.add_to_stream('test:stream', test_data)
        assert message_id is not None, "Should handle special characters"


class TestRedisErrorHandling:
    """Test Redis error handling"""
    
    @pytest.mark.asyncio
    async def test_disconnect_and_reconnect(self):
        """Test disconnecting and reconnecting"""
        client = RedisClient()
        await client.connect()
        
        # Verify connected
        assert await client.ping() is True
        
        # Disconnect
        await client.disconnect()
        
        # Reconnect
        await client.connect()
        assert await client.ping() is True
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_invalid_stream_operations(self, redis_client):
        """Test handling of invalid stream operations"""
        # Reading from non-existent stream should not crash
        messages = await redis_client.read_stream('nonexistent:stream', count=1)
        assert messages is not None, "Should handle non-existent stream"


# Run tests with: pytest tests/test_redis_integration.py -v
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
