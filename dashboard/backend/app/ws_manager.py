"""
WebSocket Connection Manager + Notification broadcaster.
"""
import json
import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id -> list of open websockets
        self._connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        conns = self._connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(user_id, None)

    async def broadcast(self, event: dict, user_ids: List[int] | None = None):
        """Send event to specific users, or all connected users if user_ids is None."""
        targets = user_ids if user_ids is not None else list(self._connections.keys())
        dead = []
        for uid in targets:
            for ws in list(self._connections.get(uid, [])):
                try:
                    await ws.send_text(json.dumps(event))
                except Exception:
                    dead.append((uid, ws))
        for uid, ws in dead:
            self.disconnect(ws, uid)


manager = ConnectionManager()


async def broadcast_notification(notification: dict, user_ids: List[int] | None = None):
    """Broadcast a notification event to all (or specific) connected users."""
    await manager.broadcast({"type": "notification", "payload": notification}, user_ids)
