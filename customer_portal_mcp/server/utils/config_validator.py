"""Config validator — fail fast on startup"""
import logging
import sys
import os

logger = logging.getLogger(__name__)


def validate_config(config):
    errors = []

    port = config.get('server.port', 8000)
    if not isinstance(port, int) or not (1 <= port <= 65535):
        errors.append(f"Invalid server.port: {port}")

    if not config.get('mcp.name'):
        errors.append("mcp.name is required")

    for key in ('database.host', 'database.name', 'database.user', 'database.password'):
        if not config.get(key):
            errors.append(f"Missing required config: {key}")

    if errors:
        for e in errors:
            logger.error(f"❌ {e}")
        sys.exit(1)

    logger.info("✅ Configuration validation passed")
