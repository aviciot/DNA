"""
Notifications API — REST + WebSocket
"""
import logging
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from ..database import get_db_pool
from ..auth import get_current_user, verify_token
from ..config import settings
from ..ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Notifications"])


# ---------------------------------------------------------------------------
# WebSocket  /ws/notifications
# ---------------------------------------------------------------------------

@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return
    try:
        user = await verify_token(token)
        user_id = user.get("user_id")
        if not user_id:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()  # keep alive, ignore client messages
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


# ---------------------------------------------------------------------------
# GET /api/v1/notifications
# ---------------------------------------------------------------------------

@router.get("/api/v1/notifications")
async def get_notifications(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("user_id")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT
                n.id, n.type, n.severity, n.title, n.message,
                n.customer_id, n.customer_name, n.task_id,
                n.created_by_name, n.created_at,
                COALESCE(nr.read_at IS NOT NULL, false) AS read,
                COALESCE(nr.dismissed, false) AS dismissed
            FROM {settings.DATABASE_APP_SCHEMA}.notifications n
            LEFT JOIN {settings.DATABASE_APP_SCHEMA}.notification_reads nr
                ON nr.notification_id = n.id AND nr.user_id = $1
            WHERE COALESCE(nr.dismissed, false) = false
            ORDER BY n.created_at DESC
            LIMIT $2
        """, user_id, limit)
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# PATCH /api/v1/notifications/{id}/read
# ---------------------------------------------------------------------------

@router.patch("/api/v1/notifications/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("user_id")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.notification_reads
                (notification_id, user_id, read_at, dismissed)
            VALUES ($1, $2, NOW(), false)
            ON CONFLICT (notification_id, user_id) DO UPDATE SET read_at = NOW()
        """, notification_id, user_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# PATCH /api/v1/notifications/{id}/dismiss
# ---------------------------------------------------------------------------

@router.patch("/api/v1/notifications/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("user_id")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.notification_reads
                (notification_id, user_id, read_at, dismissed)
            VALUES ($1, $2, NOW(), true)
            ON CONFLICT (notification_id, user_id) DO UPDATE SET dismissed = true
        """, notification_id, user_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# PATCH /api/v1/notifications/dismiss-all
# ---------------------------------------------------------------------------

@router.patch("/api/v1/notifications/dismiss-all")
async def dismiss_all(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("user_id")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.notification_reads
                (notification_id, user_id, read_at, dismissed)
            SELECT id, $1, NOW(), true
            FROM {settings.DATABASE_APP_SCHEMA}.notifications
            ON CONFLICT (notification_id, user_id) DO UPDATE SET dismissed = true
        """, user_id)
    return {"ok": True}
