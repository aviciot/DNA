"""
WebSocket handlers for DNA backend.

Provides real-time communication endpoints for:
- Task progress updates (task_progress.websocket_endpoint)
"""

from .task_progress import websocket_endpoint

__all__ = ['websocket_endpoint']
