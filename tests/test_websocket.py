"""
Test WebSocket Progress Relay
==============================

Tests that WebSocket receives messages published to Redis Pub/Sub.
"""

import asyncio
import json
import websockets
import redis.asyncio as redis


async def test_websocket_progress():
    """Test WebSocket receives progress updates from Redis."""
    task_id = "test-task-123"
    ws_url = f"ws://localhost:8400/ws/tasks/{task_id}"
    redis_url = "redis://localhost:6379"

    print(f"Testing WebSocket progress relay for task: {task_id}")
    print(f"WebSocket URL: {ws_url}")
    print(f"Redis channel: progress:task:{task_id}")
    print("-" * 60)

    # Connect to Redis
    redis_client = await redis.from_url(redis_url, decode_responses=True)

    try:
        # Connect to WebSocket
        async with websockets.connect(ws_url) as websocket:
            print("[OK] WebSocket connected")

            # Wait for connection confirmation
            initial_msg = await websocket.recv()
            print(f"[RX] Received: {initial_msg}")

            # Publish test messages to Redis
            test_messages = [
                {"progress": 25, "current_step": "Loading document...", "timestamp": "2026-02-07T10:57:00Z"},
                {"progress": 50, "current_step": "Analyzing structure...", "timestamp": "2026-02-07T10:57:05Z"},
                {"progress": 75, "current_step": "Validating fields...", "timestamp": "2026-02-07T10:57:10Z"},
                {"progress": 100, "current_step": "Complete!", "timestamp": "2026-02-07T10:57:15Z"}
            ]

            print("\n[TX] Publishing messages to Redis...")
            for msg in test_messages:
                # Publish to Redis
                channel = f"progress:task:{task_id}"
                await redis_client.publish(channel, json.dumps(msg))
                print(f"  -> Published: {msg}")

                # Wait for WebSocket to receive
                try:
                    ws_msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    ws_data = json.loads(ws_msg)
                    print(f"  [OK] Received via WebSocket: {ws_data}")

                    # Validate message
                    assert ws_data["type"] == "progress", "Message type should be 'progress'"
                    assert ws_data["task_id"] == task_id, "Task ID should match"
                    assert ws_data["progress"] == msg["progress"], "Progress should match"
                    assert ws_data["current_step"] == msg["current_step"], "Step should match"

                except asyncio.TimeoutError:
                    print("  [ERROR] Timeout waiting for WebSocket message")
                    return False

                # Small delay between messages
                await asyncio.sleep(0.5)

            print("\n" + "=" * 60)
            print("ALL TESTS PASSED")
            print("=" * 60)
            return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    # Run test
    success = asyncio.run(test_websocket_progress())
    exit(0 if success else 1)
