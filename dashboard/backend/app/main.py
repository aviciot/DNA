"""
DNA Backend - Main Application
===============================
"""

import logging
from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import settings
from .database import get_db_pool, close_db_pool
from .auth import get_current_user, verify_token
from .chat import chat_service
from .routes import customers, templates

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

# Include routers
app.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["Templates"])


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

    logger.info(f"Service started on {settings.HOST}:{settings.PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down DNA Backend API")
    await close_db_pool()
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
    except:
        db_status = "error"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "service": "DNA Backend API",
        "version": "1.0.0",
        "database": db_status
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


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
