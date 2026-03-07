"""Customer Portal MCP Server"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import signal
import logging
import importlib
import pkgutil
import warnings
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
import uvicorn

from config import get_config
from mcp_app import mcp
from auth_middleware import AuthMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

config = get_config()

from utils.config_validator import validate_config
validate_config(config)

AUTO_DISCOVER = os.getenv("AUTO_DISCOVER", "true").lower() in ("1", "true", "yes", "on")


def import_submodules(pkg_name: str):
    try:
        pkg = __import__(pkg_name)
        for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            if not ispkg and not modname.startswith('_'):
                full = f"{pkg_name}.{modname}"
                importlib.import_module(full)
                logger.info(f"✅ Loaded: {full}")
    except Exception as e:
        logger.error(f"❌ Failed to load {pkg_name}: {e}")


def _shutdown(*_):
    logger.info("🛑 Shutting down...")
    sys.exit(0)

for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _shutdown)

logger.info("=" * 60)
logger.info("🚀 Customer Portal MCP — Starting")
logger.info("=" * 60)

if AUTO_DISCOVER:
    for pkg in ("tools", "resources", "prompts"):
        import_submodules(pkg)

logger.info("📡 MCP Server: Ready")

# ── DB lifespan ──────────────────────────────────────────────
from db.connector import db

mcp_http_app = mcp.http_app(transport="streamable-http")

@asynccontextmanager
async def lifespan(app):
    await db.connect()
    async with mcp_http_app.lifespan(app):
        yield
    await db.disconnect()

# ── Build app ────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ["PYTHONUNBUFFERED"] = "1"

app = Starlette(lifespan=lifespan)

from utils.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthMiddleware, config=config)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


async def health(request):
    return PlainTextResponse("OK")


async def deep_health(request):
    ok = await db.health_check()
    status = {"status": "healthy" if ok else "unhealthy", "database": "ok" if ok else "error"}
    return JSONResponse(status, status_code=200 if ok else 503)


async def version(request):
    return JSONResponse({"name": config.get('mcp.name'), "version": config.get('server.version', '1.0.0'), "status": "running"})


app.add_route("/healthz", health, methods=["GET"])
app.add_route("/health", health, methods=["GET"])
app.add_route("/health/deep", deep_health, methods=["GET"])
app.add_route("/version", version, methods=["GET"])
app.mount("/", mcp_http_app)

if __name__ == "__main__":
    port = int(os.getenv('MCP_PORT', config.get('server.port', 8000)))
    uvicorn.run(app, host=config.get('server.host', '0.0.0.0'), port=port, log_level="info")
