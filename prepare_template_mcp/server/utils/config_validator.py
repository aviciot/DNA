"""
Configuration Validator
=======================
Validates configuration on startup - fails fast if misconfigured
"""

import logging
import sys
import os

logger = logging.getLogger(__name__)


def validate_config(config):
    """
    Validate configuration and fail fast if issues found
    
    Args:
        config: Config instance to validate
    
    Raises:
        SystemExit: If validation fails
    """
    errors = []
    warnings = []
    
    # Validate server configuration
    port = config.get('server.port', 8000)
    if not isinstance(port, int) or port < 1 or port > 65535:
        errors.append(f"Invalid server.port: {port} (must be 1-65535)")
    
    # Validate MCP name
    mcp_name = config.get('mcp.name')
    if not mcp_name or not isinstance(mcp_name, str):
        errors.append("mcp.name is required and must be a string")
    
    # Validate authentication if enabled
    if config.is_authentication_enabled():
        token = config.get_auth_token()
        if not token:
            errors.append("AUTH_ENABLED=true but AUTH_TOKEN is not set")
        elif len(token) < 16:
            warnings.append(f"AUTH_TOKEN is weak (only {len(token)} chars) - use at least 32 chars")
    
    # Validate environment variables
    mcp_port_env = os.getenv('MCP_PORT')
    if mcp_port_env:
        try:
            port_val = int(mcp_port_env)
            if port_val < 1 or port_val > 65535:
                errors.append(f"MCP_PORT={mcp_port_env} is invalid (must be 1-65535)")
        except ValueError:
            errors.append(f"MCP_PORT={mcp_port_env} is not a valid integer")
    
    # Report warnings
    if warnings:
        logger.warning("⚠️  Configuration Warnings:")
        for warning in warnings:
            logger.warning(f"   - {warning}")
    
    # Report errors and exit if any
    if errors:
        logger.error("❌ Configuration Validation Failed:")
        for error in errors:
            logger.error(f"   - {error}")
        logger.error("Fix configuration and restart server")
        sys.exit(1)
    
    logger.info("✅ Configuration validation passed")
