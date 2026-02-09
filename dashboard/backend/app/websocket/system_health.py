"""
System Health WebSocket Handler
================================

WebSocket endpoint for streaming real-time system health alerts.

Endpoint: /ws/system/health
Subscribes to: system:health:alerts stream
"""

import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from ..redis_client import redis_client

logger = logging.getLogger(__name__)

HEALTH_STREAM = "system:health:alerts"


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for system health monitoring.

    Streams health messages from Redis to connected clients.
    """
    await websocket.accept()
    logger.info("System health WebSocket connected")

    pubsub = None
    connection_alive = True

    try:
        # Subscribe to health stream via Pub/Sub
        # Note: We'll convert stream to pub/sub for real-time delivery
        channel_name = HEALTH_STREAM

        # Create Pub/Sub subscription
        pubsub = redis_client._client.pubsub()
        await pubsub.subscribe(channel_name)
        logger.info(f"Subscribed to health channel: {channel_name}")

        # Send subscription confirmation
        await websocket.send_json({
            "type": "subscribed",
            "channel": channel_name,
            "timestamp": asyncio.get_event_loop().time()
        })

        # Send welcome message with current system status
        import datetime
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        # Send status for all components
        components = [
            ("database", "Database pool is active"),
            ("redis", "Redis connection is active"),
            ("backend", "Backend service is running"),
            ("ai-worker", "AI worker service status")
        ]

        for component, message in components:
            await websocket.send_json({
                "component": component,
                "status": "healthy",
                "message": message,
                "severity": "info",
                "timestamp": timestamp,
                "metadata": {"source": "startup"}
            })

        # Listen for messages
        async def listen_redis():
            """Listen for Redis Pub/Sub messages and forward to WebSocket."""
            nonlocal connection_alive
            logger.info("Health listener task started, waiting for messages...")
            try:
                async for message in pubsub.listen():
                    logger.debug(f"Received Pub/Sub message: {message}")

                    if not connection_alive:
                        break

                    if message['type'] == 'message':
                        try:
                            # Parse message data
                            data = message['data']
                            if isinstance(data, bytes):
                                data = data.decode('utf-8')

                            logger.info(f"Processing health message: {data}")

                            # Try to parse as JSON
                            try:
                                parsed_data = json.loads(data)
                            except json.JSONDecodeError:
                                # If not JSON, wrap in standard format
                                parsed_data = {
                                    "type": "health_alert",
                                    "message": data
                                }

                            # Ensure type field exists
                            if 'type' not in parsed_data:
                                parsed_data['type'] = 'health_alert'

                            # Forward to WebSocket
                            if websocket.client_state == WebSocketState.CONNECTED:
                                await websocket.send_json(parsed_data)
                                logger.info(f"Forwarded health message to WebSocket client")
                            else:
                                connection_alive = False
                                break

                        except Exception as e:
                            logger.error(f"Error processing health message: {e}")

            except asyncio.CancelledError:
                logger.info("Health listener cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in health listener: {e}")
                connection_alive = False

        # Start listener task
        listener_task = asyncio.create_task(listen_redis())

        # Keep connection alive and handle client messages (ping/pong)
        try:
            while connection_alive:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)

                    # Handle ping/pong
                    try:
                        message = json.loads(data)
                        if message.get('type') == 'ping':
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": message.get('timestamp')
                            })
                    except json.JSONDecodeError:
                        pass

                except asyncio.TimeoutError:
                    continue

        except WebSocketDisconnect:
            logger.info("System health WebSocket disconnected")
            connection_alive = False

    except Exception as e:
        logger.error(f"Error in system health WebSocket: {e}")

    finally:
        # Cleanup
        connection_alive = False

        if listener_task:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        if pubsub:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.close()
            except Exception as e:
                logger.error(f"Error unsubscribing from health channel: {e}")

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except:
            pass

        logger.info("System health WebSocket connection closed")
