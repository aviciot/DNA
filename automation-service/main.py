"""
DNA Automation Service
======================
Entry point. Starts:
  - DB pool
  - Redis stream consumer (send + extract workers)
  - IMAP listener (polling)
  - APScheduler (follow-ups + expire)
"""
import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from config import settings
from db_client import get_pool, close_pool
from stream_consumer import consumer
from email_listener import IMAPListener
from scheduler import AutomationScheduler


async def main():
    logger.info("━━━ DNA Automation Service starting ━━━")

    # Init DB pool
    await get_pool()
    logger.info("✓ Database connected")

    # Init stream consumer
    await consumer.start()
    logger.info("✓ Stream consumer ready")

    # Init IMAP listener + scheduler
    listener = IMAPListener(cfg={}, on_email_callback=None)
    sched = AutomationScheduler(listener=listener)
    await sched.start(redis_url=settings.REDIS_URL)
    logger.info("✓ Scheduler started")

    logger.info("━━━ Automation service running ━━━")

    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def _shutdown(sig, _frame):
        logger.info(f"Received {signal.Signals(sig).name}, shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _shutdown)

    # Run consumer in background task
    consumer_task = asyncio.create_task(consumer.consume_forever())

    try:
        await stop_event.wait()
    finally:
        logger.info("Stopping...")
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        await consumer.stop()
        sched.stop()
        await close_pool()
        logger.info("━━━ Automation service stopped ━━━")


if __name__ == "__main__":
    asyncio.run(main())
