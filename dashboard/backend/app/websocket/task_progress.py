"""
WebSocket handler for real-time task progress updates.

This module provides a WebSocket endpoint that subscribes to Redis Pub/Sub
channels for specific task IDs and forwards progress messages to connected clients.

Endpoint: /ws/tasks/{task_id}
Redis Channel: progress:task:{task_id}
"""

import asyncio
import json
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from ..database import get_db_pool
from ..redis_client import redis_client

logger = logging.getLogger(__name__)


async def safe_send_json(websocket: WebSocket, data: dict) -> bool:
    """
    Safely send JSON to WebSocket, handling closed connections.

    Returns:
        True if send succeeded, False if connection is closed
    """
    try:
        # Check if websocket is still connected
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.debug("WebSocket not connected, skipping send")
            return False

        await websocket.send_json(data)
        return True
    except Exception as e:
        logger.debug(f"Failed to send WebSocket message: {e}")
        return False


async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for task progress updates.

    Args:
        websocket: FastAPI WebSocket connection
        task_id: Task UUID to subscribe to

    Flow:
        1. Accept WebSocket connection
        2. Verify task exists in database
        3. Subscribe to Redis Pub/Sub channel progress:task:{task_id}
        4. Forward all messages to WebSocket client
        5. Handle disconnection gracefully
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for task {task_id}")

    pubsub = None
    listener_task = None
    connection_alive = True

    # Verify task exists
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT id, status FROM dna_app.ai_tasks WHERE id = $1",
                task_id
            )

        if not result:
            await safe_send_json(websocket, {
                "type": "error",
                "message": f"Task {task_id} not found"
            })
            await websocket.close()
            logger.warning(f"Task {task_id} not found, closing WebSocket")
            return

        task_status = result['status']

        # Send initial task status
        if not await safe_send_json(websocket, {
            "type": "task_status",
            "task_id": task_id,
            "status": task_status
        }):
            logger.warning(f"Failed to send initial status for task {task_id}")
            return

        # If task is already completed/failed/cancelled, fetch full data and send completion
        if task_status in ['completed', 'failed', 'cancelled']:
            # Fetch full task data to include elapsed time and result summary
            async with pool.acquire() as conn:
                full_task = await conn.fetchrow("""
                    SELECT
                        id, status, error,
                        result, created_at, completed_at
                    FROM dna_app.ai_tasks
                    WHERE id = $1
                """, task_id)

            # Calculate elapsed seconds if we have timestamps
            elapsed_seconds = 0
            if full_task and full_task['created_at'] and full_task['completed_at']:
                elapsed_seconds = int((full_task['completed_at'] - full_task['created_at']).total_seconds())

            # Build completion message
            completion_msg = {
                "type": "task_complete",
                "task_id": task_id,
                "status": task_status,
                "elapsed_seconds": elapsed_seconds,
                "current_step": "Completed!" if task_status == 'completed' else "Failed"
            }

            # Add result_summary if task completed successfully
            if task_status == 'completed' and full_task and full_task['result']:
                try:
                    # Result is already JSONB in database, no need to parse
                    result_data = full_task['result']
                    if isinstance(result_data, dict) and 'result_summary' in result_data:
                        completion_msg['result_summary'] = result_data['result_summary']
                except Exception as parse_error:
                    logger.warning(f"Failed to extract result_summary for task {task_id}: {parse_error}")

            # Add error details if task failed
            if task_status == 'failed' and full_task and full_task['error']:
                completion_msg['error'] = full_task['error']
                completion_msg['error_type'] = 'task_error'  # Generic type since we don't store error_type

            await safe_send_json(websocket, completion_msg)
            logger.info(f"Task {task_id} already {task_status}, sent full completion data, closing WebSocket")
            await websocket.close()
            return

    except Exception as e:
        logger.error(f"Error verifying task {task_id}: {e}")
        await safe_send_json(websocket, {
            "type": "error",
            "message": "Failed to verify task"
        })
        try:
            await websocket.close()
        except:
            pass
        return

    # Subscribe to Redis Pub/Sub channel
    channel_name = f"progress:task:{task_id}"

    try:
        # Create Pub/Sub subscription
        pubsub = redis_client._client.pubsub()
        await pubsub.subscribe(channel_name)
        logger.info(f"Subscribed to Redis channel: {channel_name}")

        # Send subscription confirmation
        if not await safe_send_json(websocket, {
            "type": "subscribed",
            "task_id": task_id,
            "channel": channel_name
        }):
            logger.warning(f"Failed to send subscription confirmation for task {task_id}")
            connection_alive = False
            return

        # Create listener task for Redis messages
        async def listen_redis():
            """Listen for Redis Pub/Sub messages and forward to WebSocket."""
            nonlocal connection_alive
            try:
                async for message in pubsub.listen():
                    # Stop if connection is dead
                    if not connection_alive:
                        logger.info(f"Connection dead, stopping Redis listener for task {task_id}")
                        break

                    if message['type'] == 'message':
                        try:
                            # Parse message data
                            data = message['data']
                            if isinstance(data, bytes):
                                data = data.decode('utf-8')

                            # Try to parse as JSON
                            try:
                                parsed_data = json.loads(data)
                            except json.JSONDecodeError:
                                # If not JSON, wrap in standard format
                                parsed_data = {
                                    "type": "progress_update",
                                    "task_id": task_id,
                                    "message": data
                                }

                            # Ensure type field exists
                            if 'type' not in parsed_data:
                                parsed_data['type'] = 'progress_update'

                            # Ensure task_id field exists
                            if 'task_id' not in parsed_data:
                                parsed_data['task_id'] = task_id

                            # Forward to WebSocket (safely)
                            if not await safe_send_json(websocket, parsed_data):
                                logger.warning(f"Failed to send message to client for task {task_id}, stopping listener")
                                connection_alive = False
                                break

                            logger.debug(f"Forwarded message to WebSocket for task {task_id}")

                            # If task completed, close connection
                            if parsed_data.get('type') == 'task_complete' or \
                               parsed_data.get('status') in ['completed', 'failed', 'cancelled']:
                                logger.info(f"Task {task_id} completed, closing WebSocket")
                                connection_alive = False
                                break

                        except Exception as e:
                            logger.error(f"Error processing Redis message for task {task_id}: {e}")
                            # Try to send error, but don't crash if it fails
                            await safe_send_json(websocket, {
                                "type": "error",
                                "message": "Error processing progress update"
                            })

            except asyncio.CancelledError:
                logger.info(f"Redis listener cancelled for task {task_id}")
                raise
            except Exception as e:
                logger.error(f"Error in Redis listener for task {task_id}: {e}")
                connection_alive = False

        # Start Redis listener
        listener_task = asyncio.create_task(listen_redis())

        # Keep connection alive and handle client messages (ping/pong)
        try:
            while connection_alive:
                # Wait for client message with timeout
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)

                    # Handle ping/pong for keep-alive
                    try:
                        message = json.loads(data)
                        if message.get('type') == 'ping':
                            if not await safe_send_json(websocket, {
                                "type": "pong",
                                "timestamp": message.get('timestamp')
                            }):
                                connection_alive = False
                                break
                    except json.JSONDecodeError:
                        # Ignore non-JSON messages
                        pass

                except asyncio.TimeoutError:
                    # No message received, continue loop
                    # This allows checking connection_alive flag
                    continue

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for task {task_id}")
            connection_alive = False
        except Exception as e:
            logger.error(f"Error in WebSocket receive loop for task {task_id}: {e}")
            connection_alive = False

    except Exception as e:
        logger.error(f"Error in WebSocket handler for task {task_id}: {e}")
        await safe_send_json(websocket, {
            "type": "error",
            "message": "Internal server error"
        })

    finally:
        # Mark connection as dead
        connection_alive = False

        # Cleanup Redis listener
        if listener_task:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        # Cleanup Redis subscription
        if pubsub:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.close()
                logger.info(f"Unsubscribed from Redis channel: {channel_name}")
            except Exception as e:
                logger.error(f"Error unsubscribing from Redis: {e}")

        # Close WebSocket
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception as e:
            logger.debug(f"Error closing websocket: {e}")

        logger.info(f"WebSocket connection closed for task {task_id}")
