"""
Health Message Publisher
========================

Publishes component health status messages to Redis Pub/Sub for real-time monitoring.

Channel: system:health:alerts
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from ..redis_client import redis_client

logger = logging.getLogger(__name__)

# Redis channel for health alerts (using Pub/Sub for immediate delivery)
HEALTH_CHANNEL = "system:health:alerts"


class HealthPublisher:
    """Publishes health status messages to Redis Pub/Sub."""

    @staticmethod
    async def publish(
        component: str,
        status: str,
        message: str,
        severity: str = "info",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Publish a health message to the Pub/Sub channel.

        Args:
            component: Component name (e.g., "database", "redis", "ai-worker", "backend")
            status: Status (e.g., "healthy", "warning", "error", "critical")
            message: Human-readable message
            severity: Severity level ("info", "warning", "error", "critical")
            metadata: Optional additional data (dict)
        """
        try:
            health_message = {
                "component": component,
                "status": status,
                "message": message,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": metadata or {}
            }

            # Publish to Redis Pub/Sub channel
            serialized = json.dumps(health_message)
            await redis_client._client.publish(HEALTH_CHANNEL, serialized)

            logger.debug(f"Health: {component} - {status} - {message}")

        except Exception as e:
            # Don't let health monitoring failures break the application
            logger.error(f"Failed to publish health message: {e}")


# Convenience functions for common statuses
async def publish_healthy(component: str, message: str, metadata: Optional[Dict] = None):
    """Publish a healthy status message."""
    await HealthPublisher.publish(component, "healthy", message, "info", metadata)


async def publish_warning(component: str, message: str, metadata: Optional[Dict] = None):
    """Publish a warning status message."""
    await HealthPublisher.publish(component, "warning", message, "warning", metadata)


async def publish_error(component: str, message: str, metadata: Optional[Dict] = None):
    """Publish an error status message."""
    await HealthPublisher.publish(component, "error", message, "error", metadata)


async def publish_critical(component: str, message: str, metadata: Optional[Dict] = None):
    """Publish a critical status message."""
    await HealthPublisher.publish(component, "critical", message, "critical", metadata)
