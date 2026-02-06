"""
DNA Backend - Database Connection
==================================
"""

import asyncpg
import logging
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global _db_pool

    if _db_pool is None:
        try:
            _db_pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=5,
                max_size=20
            )
            logger.info("Database pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    return _db_pool


async def close_db_pool() -> None:
    """Close database connection pool."""
    global _db_pool

    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database pool closed")
