"""
Zombie Task Cleanup Job
=======================

Background job that detects and cleans up stuck/zombie tasks.

A task is considered a zombie if:
1. Status = 'processing' AND started_at > 15 minutes ago
2. Status = 'pending' AND created_at > 20 minutes ago

These tasks are marked as 'failed' with an appropriate error message.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from db_client import db_client

logger = logging.getLogger(__name__)


async def cleanup_zombie_tasks():
    """
    Detect and cleanup zombie tasks.

    Runs periodically to find tasks that are stuck and mark them as failed.
    """
    try:
        # Ensure database connection exists
        if not db_client._pool:
            logger.warning("Database pool not initialized, skipping cleanup")
            return

        # Find processing tasks stuck for >15 minutes
        async with db_client._pool.acquire() as conn:
            processing_zombies = await conn.fetch("""
                UPDATE dna_app.ai_tasks
                SET
                    status = 'failed',
                    error = 'Task timed out after 15 minutes - worker may have crashed',
                    completed_at = NOW()
                WHERE status = 'processing'
                  AND started_at < NOW() - INTERVAL '15 minutes'
                RETURNING id, task_type
            """)

        if processing_zombies:
            logger.warning(f"Cleaned up {len(processing_zombies)} zombie processing tasks")
            for zombie in processing_zombies:
                logger.warning(f"  - Task {zombie['id']} ({zombie['task_type']}) timed out")

        # Find pending tasks stuck for >20 minutes
        async with db_client._pool.acquire() as conn:
            pending_zombies = await conn.fetch("""
                UPDATE dna_app.ai_tasks
                SET
                    status = 'failed',
                    error = 'Task never started after 20 minutes - no worker available',
                    completed_at = NOW()
                WHERE status = 'pending'
                  AND created_at < NOW() - INTERVAL '20 minutes'
                RETURNING id, task_type
            """)

        if pending_zombies:
            logger.warning(f"Cleaned up {len(pending_zombies)} zombie pending tasks")
            for zombie in pending_zombies:
                logger.warning(f"  - Task {zombie['id']} ({zombie['task_type']}) never started")

        if processing_zombies or pending_zombies:
            total = len(processing_zombies) + len(pending_zombies)
            logger.info(f"✓ Zombie cleanup complete: {total} tasks marked as failed")

    except Exception as e:
        logger.error(f"Error during zombie task cleanup: {e}")


async def run_cleanup_loop(interval_seconds: int = 300):
    """
    Run cleanup job in an infinite loop.

    Args:
        interval_seconds: How often to run cleanup (default: 300 = 5 minutes)
    """
    logger.info(f"Starting zombie task cleanup job (interval: {interval_seconds}s)")

    while True:
        try:
            await cleanup_zombie_tasks()
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Zombie cleanup job cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in cleanup loop: {e}")
            await asyncio.sleep(interval_seconds)  # Still wait before retrying
