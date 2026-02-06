"""
Template MCP Server - Starlette Application
===========================================
MCP server with authentication middleware and auto-discovery
"""

import os
import sys

# Add parent directory to path to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import signal
import logging
import importlib
import pkgutil
import warnings

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
import uvicorn

from config import get_config
from mcp_app import mcp

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
config = get_config()

# Validate configuration (fail fast if misconfigured)
from utils.config_validator import validate_config
validate_config(config)

# ========================================
# AUTO-DISCOVERY CONFIGURATION
# ========================================
AUTO_DISCOVER = os.getenv("AUTO_DISCOVER", "true").lower() in ("1", "true", "yes", "on")

# ========================================
# MODULE LOADING HELPERS
# ========================================
def import_submodules(pkg_name: str):
    """Auto-import all submodules in a package (tools/resources/prompts)."""
    try:
        pkg = __import__(pkg_name)
        for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            if not ispkg and not modname.startswith('_'):
                full_name = f"{pkg_name}.{modname}"
                importlib.import_module(full_name)
                logger.info(f"✅ Loaded: {full_name}")
    except Exception as e:
        logger.error(f"❌ Failed to load {pkg_name}: {e}")

def safe_import(name: str):
    """Static import (fallback when AUTO_DISCOVER disabled)."""
    try:
        module = __import__(name, fromlist=["*"])
        logger.info(f"✅ Imported: {name}")
        return module
    except Exception as e:
        logger.exception(f"❌ Failed to import: {name}: {e}")
        raise

# ========================================
# GRACEFUL SHUTDOWN
# ========================================
def _graceful_shutdown(*_):
    logger.info("🛑 Received shutdown signal, stopping gracefully...")
    sys.exit(0)

for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _graceful_shutdown)

# ========================================
# STARTUP BANNER
# ========================================
logger.info("=" * 80)
logger.info("🚀 Template MCP Server - Starting Up")
logger.info("=" * 80)
logger.info(f"📦 Version: {config.get('server.version', '1.0.0')}")
logger.info(f"🌐 Port: {os.getenv('MCP_PORT', config.get('server.port', 8000))}")

# Authentication status
auth_enabled = config.is_authentication_enabled()
auth_icon = "✅" if auth_enabled else "❌"
logger.info(f"🔐 Authentication: {auth_icon} {'Enabled' if auth_enabled else 'Disabled'}")

logger.info("-" * 80)

# ========================================
# AUTO-DISCOVER MODULES
# ========================================
if AUTO_DISCOVER:
    logger.info("🔍 Auto-discovery enabled - loading all tools/resources/prompts...")
    for pkg in ("tools", "resources", "prompts"):
        import_submodules(pkg)
else:
    logger.info("📦 Using static imports...")
    for pkg in ("tools", "resources", "prompts"):
        safe_import(pkg)

logger.info("-" * 80)
logger.info("📡 MCP Server: Ready")
logger.info("=" * 80)

# ========================================
# BUILD ASGI APP
# ========================================
os.environ["PYTHONUNBUFFERED"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)

from contextlib import asynccontextmanager

# Knowledge DB initialization
async def init_knowledge_db():
    """Initialize knowledge DB connection (required for admin features and feedback)."""
    from knowledge_db import get_knowledge_db

    logger.info("🔗 Initializing MCP Knowledge DB...")
    db = get_knowledge_db()
    if db.config is None:
        logger.warning("⚠️  MCP knowledge DB: Config loading failed - continuing without knowledge DB")
        return

    success = await db.init()
    if success and db.is_enabled:
        logger.info("✅ MCP knowledge DB connection: SUCCESS")

        # Initialize feedback safety manager with database pool
        try:
            from tools.feedback_safety_db import initialize_safety_manager
            initialize_safety_manager(db.pool)
            logger.info("✅ Feedback safety manager initialized with database storage")
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize feedback safety manager with DB: {e}")

        # Get cache stats for diagnostic info
        try:
            stats = await db.get_cache_stats()
            logger.info(f"   📊 Cache stats: {stats.get('tables_cached', 0)} tables, {stats.get('relationships_cached', 0)} relationships")

            # Warm cache for better performance
            if stats.get('tables_cached', 0) > 0:
                logger.info("🔥 Warming cache with frequently accessed tables...")
                warm_stats = await db.warm_cache_on_startup(top_n=50)
                logger.info(f"   🔥 Cache warmed: {warm_stats.get('warmed', 0)} tables, {warm_stats.get('relationships_warmed', 0)} relationships")
                if warm_stats.get('top_domains'):
                    logger.info(f"   🏷️  Top domains: {', '.join(warm_stats['top_domains'][:5])}")
        except Exception as stats_error:
            logger.warning(f"   ⚠️  Could not get cache stats: {stats_error}")
    else:
        logger.warning("⚠️  MCP knowledge DB connection: FAILED - continuing without knowledge DB")
        status = db.get_connection_status()
        logger.debug(f"   Connection status: {status}")

@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager - runs on startup and shutdown."""
    # Startup: Initialize Knowledge DB
    try:
        await init_knowledge_db()
    except Exception as e:
        logger.error(f"❌ MCP knowledge DB initialization failed: {e}", exc_info=True)
        logger.warning("⚠️  Continuing without knowledge DB (admin features may not work)")

    yield

    # Shutdown: Cleanup Knowledge DB
    try:
        from knowledge_db import cleanup_knowledge_db
        await cleanup_knowledge_db()
        logger.info("✅ Knowledge DB cleanup complete")
    except Exception as e:
        logger.error(f"⚠️  Error during Knowledge DB cleanup: {e}")

# Get FastMCP HTTP app
mcp_http_app = mcp.http_app()

# Wrap the MCP lifespan with our own lifespan
@asynccontextmanager
async def combined_lifespan(app):
    """Combined lifespan for both MCP and Knowledge DB."""
    # Start our lifespan
    async with lifespan(app):
        # Start MCP lifespan
        async with mcp_http_app.lifespan(app):
            yield

app = Starlette(lifespan=combined_lifespan)


# ========================================
# AUTHENTICATION MIDDLEWARE
# ========================================
class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware - validates Bearer token"""

    async def dispatch(self, request, call_next):
        # Skip auth for health check and info endpoints
        if request.url.path in ["/healthz", "/health", "/version", "/_info"]:
            return await call_next(request)

        # Check if authentication is enabled
        if not config.is_authentication_enabled():
            logger.debug("Authentication disabled - allowing request")
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("Missing Authorization header")
            return JSONResponse(
                {"error": "Missing Authorization header"},
                status_code=401
            )

        # Validate Bearer token format
        if not auth_header.startswith("Bearer "):
            logger.warning("Invalid Authorization header format")
            return JSONResponse(
                {"error": "Invalid Authorization header format. Use: Bearer <token>"},
                status_code=401
            )

        # Extract and validate token
        token = auth_header[7:]  # Remove "Bearer " prefix
        expected_token = config.get_auth_token()

        if token != expected_token:
            logger.warning("Invalid authentication token")
            return JSONResponse(
                {"error": "Invalid authentication token"},
                status_code=403
            )

        # Token valid - proceed
        logger.debug("Authentication successful")
        return await call_next(request)


# ========================================
# SESSION CONTEXT MIDDLEWARE (for Feedback System)
# ========================================
class SessionContextMiddleware(BaseHTTPMiddleware):
    """
    Sets session and client context variables for feedback tracking.

    Only active when feedback system is enabled in settings.yaml.
    Extracts session ID from request headers and sets context variables
    for use in feedback tools.
    """

    async def dispatch(self, request, call_next):
        # Only activate if feedback system is enabled
        if not config.is_feedback_enabled():
            return await call_next(request)

        try:
            # Import here to avoid circular dependency
            from tools.feedback_context import set_request_context

            # Extract session ID from headers (if provided by MCP client)
            session_id = request.headers.get("X-Session-ID") or request.headers.get("X-Request-ID")

            # If no session ID provided, generate one from connection info
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())

            # Extract client ID (from auth token or default)
            client_id = "anonymous"
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                # In production, you'd decode the token to get actual client_id
                # For now, use a hash of the token as client_id
                import hashlib
                token = auth_header[7:]
                client_id = hashlib.md5(token.encode()).hexdigest()[:16]

            # Set context for this request
            set_request_context(
                session_id=session_id,
                user_id=client_id,
                client_id=client_id
            )

        except Exception as e:
            logger.warning(f"Failed to set session context: {e}")

        return await call_next(request)


# Add authentication middleware if enabled
if config.is_authentication_enabled():
    app.add_middleware(AuthenticationMiddleware)
    logger.info("Authentication middleware enabled")

# Add session context middleware (for feedback system)
if config.is_feedback_enabled():
    app.add_middleware(SessionContextMiddleware)
    logger.info("Session context middleware enabled (feedback system active)")

# Add request logging middleware
from utils.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
logger.info("Request logging middleware enabled")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# SIMPLE ENDPOINTS
# ========================================

async def health_check(request):
    """Health check endpoint"""
    return PlainTextResponse("OK")


async def version_info(request):
    """Version information endpoint"""
    return JSONResponse({
        "name": config.get('mcp.name', 'template-mcp'),
        "version": config.get('server.version', '1.0.0'),
        "status": "running"
    })


async def deep_health_check(request):
    """
    Deep health check - checks dependencies
    
    Returns 200 if all dependencies are healthy, 503 otherwise
    """
    health = {
        "status": "healthy",
        "checks": {
            "server": "ok"
        }
    }
    
    # Add database health check if you have DB
    # try:
    #     from db.connector import db
    #     if await db.health_check():
    #         health["checks"]["database"] = "ok"
    #     else:
    #         health["checks"]["database"] = "unhealthy"
    #         health["status"] = "unhealthy"
    # except Exception as e:
    #     health["checks"]["database"] = f"error: {str(e)}"
    #     health["status"] = "unhealthy"
    
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(health, status_code=status_code)


# ========================================
# ROUTES
# ========================================
app.add_route("/healthz", health_check, methods=["GET"])
app.add_route("/health", health_check, methods=["GET"])
app.add_route("/health/deep", deep_health_check, methods=["GET"])
app.add_route("/version", version_info, methods=["GET"])

# ========================================
# MOUNT FASTMCP HTTP APP
# ========================================
# Mount FastMCP at root
app.mount("/", mcp_http_app)

logger.info("✅ FastMCP mounted at /")

# ========================================
# MAIN
# ========================================
if __name__ == "__main__":
    port = int(os.getenv('MCP_PORT', config.get('server.port', 8000)))
    host = config.get('server.host', '0.0.0.0')
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
