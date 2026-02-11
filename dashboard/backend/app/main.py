"""
DNA Backend - Main Application
===============================
"""

import logging
from fastapi import FastAPI, WebSocket, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import settings
from .database import get_db_pool, close_db_pool
from .redis_client import redis_client
from .auth import get_current_user, verify_token
from .chat import chat_service
from .routes import customers, templates, tasks, iso_standards, template_files, catalog_templates, iso_customers, iso_plans, template_preview
from .websocket import websocket_endpoint
from .websocket.system_health import websocket_endpoint as system_health_websocket
from .health.publisher import publish_healthy, publish_error, publish_critical

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DNA Backend API",
    description="Backend service for DNA ISO Certification Dashboard",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to handle OPTIONS requests (CORS preflight)
@app.middleware("http")
async def options_middleware(request: Request, call_next):
    """Handle OPTIONS requests for CORS preflight."""
    if request.method == "OPTIONS":
        from fastapi.responses import Response
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Credentials": "true",
            }
        )
    return await call_next(request)

# Include routers
app.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])
app.include_router(iso_customers.router, prefix="/api/v1")  # ISO Customer Management
app.include_router(iso_plans.router, prefix="/api/v1")  # ISO Plans Management
app.include_router(templates.router, prefix="/api/v1/templates", tags=["Templates"])
app.include_router(tasks.router)
app.include_router(iso_standards.router, prefix="/api/v1")
app.include_router(template_files.router, prefix="/api/v1")
app.include_router(catalog_templates.router, prefix="/api/v1")
app.include_router(template_preview.router)  # Template Preview (Phase 1 POC)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting DNA Backend API")

    # Validate settings
    try:
        settings.validate()
        logger.info("Configuration validated")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    # Initialize database pool
    try:
        await get_db_pool()
        logger.info("Database pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Initialize Redis connection
    try:
        await redis_client.connect()
        if await redis_client.ping():
            logger.info("Redis connection initialized")
        else:
            logger.warning("Redis ping failed")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise

    # Now that Redis is connected, publish health status
    try:
        await publish_healthy("database", "Database pool initialized successfully")
        await publish_healthy("redis", "Redis connection established successfully")
        await publish_healthy("backend", f"Backend service started on {settings.HOST}:{settings.PORT}")
    except Exception as e:
        logger.warning(f"Failed to publish initial health status: {e}")

    logger.info(f"Service started on {settings.HOST}:{settings.PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down DNA Backend API")
    await publish_healthy("backend", "Backend service shutting down gracefully")
    await close_db_pool()
    await redis_client.disconnect()
    logger.info("Shutdown complete")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_status = "disconnected"
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = "error"
        await publish_error("database", f"Health check failed: {e}")

    redis_status = "disconnected"
    try:
        if await redis_client.ping():
            redis_status = "connected"
    except Exception as e:
        redis_status = "error"
        await publish_error("redis", f"Health check failed: {e}")

    overall_healthy = (db_status == "connected" and redis_status == "connected")

    if not overall_healthy:
        await publish_error("backend", f"System unhealthy - DB: {db_status}, Redis: {redis_status}")

    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "service": "DNA Backend API",
        "version": "1.0.0",
        "database": db_status,
        "redis": redis_status
    }


@app.get("/api/v1/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """
    Get dashboard statistics.
    
    Requires authentication.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Get stats from database
            total_customers = await conn.fetchval("SELECT COUNT(*) FROM dna_app.customers") or 0
            active_documents = await conn.fetchval("SELECT COUNT(*) FROM dna_app.documents WHERE status IN ('draft', 'in_progress', 'review')") or 0
            pending_tasks = await conn.fetchval("SELECT COUNT(*) FROM dna_app.ai_tasks WHERE status = 'pending'") or 0
            
            # Calculate completion rate
            total_docs = await conn.fetchval("SELECT COUNT(*) FROM dna_app.documents") or 1
            completed_docs = await conn.fetchval("SELECT COUNT(*) FROM dna_app.documents WHERE status = 'completed'") or 0
            completion_rate = round((completed_docs / total_docs) * 100, 1) if total_docs > 0 else 0

        return {
            "total_customers": total_customers,
            "active_documents": active_documents,
            "pending_tasks": pending_tasks,
            "completion_rate": completion_rate
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(500, "Failed to fetch dashboard statistics")


@app.get("/api/v1/config/admin")
async def get_admin_config(user: dict = Depends(get_current_user)):
    """
    Get admin configuration (admin only).
    """
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")

    return {
        "debug_mode": settings.ENV == "development",
        "anthropic_model": settings.ANTHROPIC_MODEL,
        "database_schema": settings.DATABASE_APP_SCHEMA
    }


@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for chat with Claude.
    
    Requires authentication via query parameter: ?token=<jwt_token>
    """
    await websocket.accept()
    
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_json({"type": "error", "content": "Authentication required"})
            await websocket.close()
            return

        # Verify token
        user = await verify_token(token)
        user_id = user.get("user_id")
        
        if not user_id:
            await websocket.send_json({"type": "error", "content": "Invalid token"})
            await websocket.close()
            return

        # Handle chat
        await chat_service.handle_chat(websocket, user_id)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except:
            pass
        finally:
            await websocket.close()


@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task progress updates.

    Subscribes to Redis Pub/Sub channel: progress:task:{task_id}
    Forwards all progress messages to connected WebSocket client.

    No authentication required (task_id acts as secret).
    """
    await websocket_endpoint(websocket, task_id)


@app.websocket("/ws/system/health")
async def websocket_system_health(websocket: WebSocket):
    """
    WebSocket endpoint for system health monitoring.

    Subscribes to Redis stream: system:health:alerts
    Forwards all health messages to connected WebSocket client.

    No authentication required for monitoring.
    """
    await system_health_websocket(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
