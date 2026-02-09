"""
Redis Client for AI Service
============================

Handles Redis Streams (task queue) and Pub/Sub (progress updates).
"""

import json
import logging
from typing import Any, Dict, List, Optional
import redis.asyncio as redis
from config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for AI service."""

    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20
            )
            self._client = redis.Redis(connection_pool=self._pool)
            logger.info(f"Redis connected to {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    async def disconnect(self):
        """Close Redis connection pool."""
        if self._client:
            await self._client.aclose()
        if self._pool:
            await self._pool.aclose()
        logger.info("Redis disconnected")

    async def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    # ============================================================
    # Redis Streams (Task Queue - Consumer)
    # ============================================================

    async def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
        start_id: str = "0"
    ):
        """
        Create consumer group for stream.

        Args:
            stream_name: Name of the stream (e.g., 'template:parse')
            group_name: Consumer group name (e.g., 'parser-workers')
            start_id: Starting message ID (0 = from beginning, $ = from latest)
        """
        try:
            await self._client.xgroup_create(
                stream_name,
                group_name,
                id=start_id,
                mkstream=True
            )
            logger.info(f"Created consumer group '{group_name}' for stream '{stream_name}'")

        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group '{group_name}' already exists")
            else:
                raise

    async def read_stream_group(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 1,
        block: int = 5000
    ) -> List[tuple]:
        """
        Read messages from Redis Stream as part of consumer group.

        Args:
            stream_name: Name of the stream
            group_name: Consumer group name
            consumer_name: Unique consumer identifier
            count: Number of messages to read
            block: Block time in milliseconds (0 = don't block)

        Returns:
            List of (stream_name, messages) tuples
            Messages format: [(message_id, {field: value}), ...]
        """
        try:
            messages = await self._client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_name: '>'},  # '>' means new messages only
                count=count,
                block=block
            )
            return messages

        except Exception as e:
            logger.error(f"Failed to read from stream {stream_name}: {e}")
            raise

    async def ack_message(
        self,
        stream_name: str,
        group_name: str,
        message_id: str
    ):
        """
        Acknowledge message processing completion.

        Args:
            stream_name: Name of the stream
            group_name: Consumer group name
            message_id: Message ID to acknowledge
        """
        try:
            await self._client.xack(stream_name, group_name, message_id)
            logger.debug(f"ACKed message {message_id} from {stream_name}")

        except Exception as e:
            logger.error(f"Failed to ACK message {message_id}: {e}")
            raise

    async def get_pending_messages(
        self,
        stream_name: str,
        group_name: str
    ) -> int:
        """
        Get count of pending (unacknowledged) messages.

        Args:
            stream_name: Name of the stream
            group_name: Consumer group name

        Returns:
            Number of pending messages
        """
        try:
            pending = await self._client.xpending(stream_name, group_name)
            # pending[0] is total count
            return pending['pending'] if isinstance(pending, dict) else pending[0]

        except Exception as e:
            logger.error(f"Failed to get pending messages: {e}")
            return 0

    # ============================================================
    # Redis Pub/Sub (Progress Updates - Publisher)
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


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency for getting Redis client."""
    if redis_client._client is None:
        await redis_client.connect()
    return redis_client
