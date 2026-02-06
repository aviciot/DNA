"""
Redis client for DNA application.
Handles Redis Streams (task queue) and Pub/Sub (progress updates).
"""

import json
import logging
from typing import Any, Optional, Dict
import redis.asyncio as redis
from .config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper for DNA application."""
    
    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        
    async def connect(self):
        """Initialize Redis connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=0,
                decode_responses=True,
                max_connections=20
            )
            self._client = redis.Redis(connection_pool=self._pool)
            logger.info(f"Redis connected to {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
    async def disconnect(self):
        """Close Redis connection pool."""
        if self._pubsub:
            await self._pubsub.close()
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis disconnected")
        
    async def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    # ============================================================
    # Redis Streams (Task Queue)
    # ============================================================
    
    async def add_to_stream(
        self, 
        stream_name: str, 
        data: Dict[str, Any],
        max_len: int = 10000
    ) -> str:
        """
        Add message to Redis Stream.
        
        Args:
            stream_name: Name of the stream (e.g., 'template:parse')
            data: Message data as dictionary
            max_len: Maximum stream length (for memory management)
            
        Returns:
            Message ID
        """
        try:
            # Convert dict values to strings for Redis
            serialized_data = {k: json.dumps(v) if not isinstance(v, str) else v 
                             for k, v in data.items()}
            
            message_id = await self._client.xadd(
                stream_name,
                serialized_data,
                maxlen=max_len,
                approximate=True
            )
            
            logger.info(f"Added message {message_id} to stream {stream_name}")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to add to stream {stream_name}: {e}")
            raise
    
    async def read_stream(
        self,
        stream_name: str,
        count: int = 10,
        block: int = 0
    ) -> list:
        """
        Read messages from Redis Stream.
        
        Args:
            stream_name: Name of the stream
            count: Number of messages to read
            block: Block time in milliseconds (0 = don't block)
            
        Returns:
            List of messages
        """
        try:
            messages = await self._client.xread(
                {stream_name: '$'},  # Read from latest
                count=count,
                block=block
            )
            return messages
            
        except Exception as e:
            logger.error(f"Failed to read from stream {stream_name}: {e}")
            raise
    
    async def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
        start_id: str = "0"
    ):
        """
        Create consumer group for stream.
        
        Args:
            stream_name: Name of the stream
            group_name: Consumer group name
            start_id: Starting message ID (0 = from beginning, $ = from latest)
        """
        try:
            await self._client.xgroup_create(
                stream_name,
                group_name,
                id=start_id,
                mkstream=True
            )
            logger.info(f"Created consumer group {group_name} for stream {stream_name}")
            
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group {group_name} already exists")
            else:
                raise
    
    async def get_stream_length(self, stream_name: str) -> int:
        """Get number of messages in stream."""
        try:
            return await self._client.xlen(stream_name)
        except Exception as e:
            logger.error(f"Failed to get stream length for {stream_name}: {e}")
            return 0
    
    # ============================================================
    # Redis Pub/Sub (Progress Updates)
    # ============================================================
    
    async def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        Publish message to Redis Pub/Sub channel.
        
        Args:
            channel: Channel name (e.g., 'progress:task:123')
            message: Message data as dictionary
            
        Returns:
            Number of subscribers that received the message
        """
        try:
            serialized = json.dumps(message)
            subscribers = await self._client.publish(channel, serialized)
            
            logger.debug(f"Published to {channel}, {subscribers} subscribers")
            return subscribers
            
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")
            raise
    
    async def subscribe(self, *channels: str):
        """
        Subscribe to Redis Pub/Sub channels.
        
        Args:
            channels: Channel names to subscribe to
            
        Returns:
            PubSub object for receiving messages
        """
        try:
            if self._pubsub is None:
                self._pubsub = self._client.pubsub()
            
            await self._pubsub.subscribe(*channels)
            logger.info(f"Subscribed to channels: {channels}")
            
            return self._pubsub
            
        except Exception as e:
            logger.error(f"Failed to subscribe to channels {channels}: {e}")
            raise
    
    async def unsubscribe(self, *channels: str):
        """Unsubscribe from channels."""
        if self._pubsub:
            await self._pubsub.unsubscribe(*channels)
            logger.info(f"Unsubscribed from channels: {channels}")
    
    # ============================================================
    # Utility Methods
    # ============================================================
    
    async def get_info(self) -> Dict[str, Any]:
        """Get Redis server info."""
        try:
            info = await self._client.info()
            return {
                'redis_version': info.get('redis_version'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'uptime_in_seconds': info.get('uptime_in_seconds')
            }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {}


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency for FastAPI endpoints."""
    if redis_client._client is None:
        await redis_client.connect()
    return redis_client
