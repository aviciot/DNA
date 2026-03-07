import asyncio
import json
import logging
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import get_pool, close_pool
from app.routes.portal import router as portal_router
from app.routes.chat import router as chat_router

logger = logging.getLogger(__name__)
HEALTH_CHANNEL = "system:health:alerts"


async def _publish(component: str, status: str, message: str, severity: str):
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.publish(HEALTH_CHANNEL, json.dumps({
            "component": component, "status": status,
            "message": message, "severity": severity,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "metadata": {},
        }))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Health publish failed: {e}")


async def _portal_health_loop():
    await asyncio.sleep(5)
    while True:
        issues = []

        # DB check
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception as e:
            issues.append(f"DB: {e}")

        # Redis check
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.aclose()
        except Exception as e:
            issues.append(f"Redis: {e}")

        # MCP check
        try:
            from fastmcp import Client
            async with Client(f"{settings.mcp_url}/mcp") as client:
                await client.list_tools()
        except Exception as e:
            issues.append(f"MCP: {e}")

        # LLM config check
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT lp.api_key FROM {settings.database_app_schema}.ai_config ac "
                    f"JOIN {settings.database_app_schema}.llm_providers lp ON lp.name = ac.provider "
                    "WHERE ac.service = 'portal_chat' AND lp.enabled = true LIMIT 1"
                )
            if not row or not row["api_key"]:
                issues.append("LLM: no provider configured")
        except Exception as e:
            issues.append(f"LLM: {e}")

        if issues:
            await _publish("customer-portal", "error", "; ".join(issues), "critical")
        else:
            await _publish("customer-portal", "healthy", "All checks passed", "info")

        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    asyncio.create_task(_portal_health_loop())
    yield
    await close_pool()


app = FastAPI(title="Customer Portal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portal_router, prefix="/portal")
app.include_router(chat_router, prefix="/portal")


@app.get("/health")
async def health():
    return {"ok": True}
