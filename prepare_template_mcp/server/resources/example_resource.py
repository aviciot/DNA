"""
Example Resource - Server Info
===============================
Demonstrates proper resource implementation with correct return format
"""

from mcp_app import mcp
from config import get_config


@mcp.resource("info://server")
async def server_info() -> str:
    """
    Get server information
    
    Returns:
        str: Server information in plain text
    """
    config = get_config()
    
    info = f"""Server Information
==================
Name: {config.get('mcp.name', 'template-mcp')}
Version: {config.get('server.version', '1.0.0')}
Port: {config.get('server.port', 8000)}
Authentication: {'Enabled' if config.is_authentication_enabled() else 'Disabled'}

Status: Running
"""
    
    # Return string directly - FastMCP handles the response format
    return info
