"""
DNA Auth Service - Health Check Route
======================================
Health endpoint for container health checks.
"""

from datetime import datetime
from fastapi import APIRouter

from models.schemas import HealthResponse
from config.settings import settings
from config.database import get_db_pool

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    # Check database connection
    db_status = "disconnected"
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        service=settings.APP_TITLE,
        version=settings.APP_VERSION,
        timestamp=datetime.now().isoformat(),
        database=db_status
    )
