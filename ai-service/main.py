"""
DNA AI Service - Main Entry Point
==================================

Background worker service that processes AI tasks from Redis Streams.

Components:
- Stream Consumer: Listens to Redis Streams for incoming tasks
- Parser Agent: Parses Word documents using Claude
- Reviewer Agent: Reviews template quality using alternative LLM
- Progress Publisher: Publishes real-time updates via Redis Pub/Sub

No HTTP server - purely a background worker.
"""

import asyncio
import logging
import signal
import sys
from config import settings
from stream_consumer import stream_consumer
from cleanup_job import run_cleanup_loop

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


class AIService:
    """Main AI service coordinator."""

    def __init__(self):
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """Start the AI service."""
        logger.info("=" * 60)
        logger.info("DNA AI Service Starting")
        logger.info("=" * 60)

        # Validate configuration
        try:
            settings.validate()
            logger.info("✓ Configuration validated")
        except ValueError as e:
            logger.error(f"✗ Configuration error: {e}")
            raise

        # Log configuration
        logger.info(f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        logger.info(f"Database: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")
        logger.info(f"Worker Concurrency: {settings.WORKER_CONCURRENCY}")
        logger.info(f"Log Level: {settings.LOG_LEVEL}")

        # Initialize stream consumer
        try:
            await stream_consumer.start()
            logger.info("✓ Stream consumer initialized")
        except Exception as e:
            logger.error(f"✗ Failed to initialize stream consumer: {e}")
            raise

        logger.info("=" * 60)
        logger.info("AI Service Started - Listening for tasks...")
        logger.info("=" * 60)

        # Start background tasks
        consumer_task = asyncio.create_task(stream_consumer.consume_forever())
        cleanup_task = asyncio.create_task(run_cleanup_loop(interval_seconds=300))  # Run every 5 minutes

        # Wait for shutdown signal or any task to complete
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(self.shutdown_event.wait()),
                consumer_task,
                cleanup_task
            ],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def stop(self):
        """Stop the AI service gracefully."""
        logger.info("Shutting down AI Service...")

        # Stop stream consumer (will close DB and Redis connections)
        await stream_consumer.stop()

        # Set shutdown event
        self.shutdown_event.set()
        logger.info("AI Service stopped")


# Global service instance
service = AIService()


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    asyncio.create_task(service.stop())


async def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
        await service.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
