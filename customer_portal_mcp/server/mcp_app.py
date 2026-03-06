"""Customer Portal MCP - FastMCP instance"""
import logging
from fastmcp import FastMCP
from config import get_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

config = get_config()
mcp = FastMCP(name=config.get('mcp.name', 'customer-portal-mcp'))
logger.info(f"Initializing {mcp.name}")
