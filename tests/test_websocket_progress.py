"""
Complete WebSocket Progress Test
=================================

Creates a task, connects via WebSocket, publishes progress, and verifies messages.
"""

import asyncio
import json
import uuid
import websockets
import redis.asyncio as redis
import asyncpg


async def test_complete_flow():
    """Test complete WebSocket flow with database task."""
    print("=" * 70)
    print("WEBSOCKET PROGRESS RELAY - COMPLETE TEST")
    print("=" * 70)

    # Configuration
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "dna",
        "user": "dna_user",
        "password": "dna_password_dev"
    }
    redis_url = "redis://localhost:6379"
    ws_url_base = "ws://localhost:8400/ws/tasks"

    task_id = str(uuid.uuid4())
    print(f"\n[1] Generated task ID: {task_id}")

    # Initialize variables for cleanup
    conn = None
    redis_client = None

    # Connect to database
    print("\n[2] Connecting to database...")
    conn = await asyncpg.connect(**db_config)

    try:
        # Create test task
        print("[3] Creating test task in database...")
        await conn.execute(
            """
            INSERT INTO dna_app.ai_tasks (
                id, task_type, status, progress, current_step,
                created_by, llm_provider, tokens_input, tokens_output
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            task_id,
            "template_parse",
            "processing",
            0,
            "Initializing...",
            1,  # User ID as integer
            "claude",
            0,
            0
        )
        print(f"    [OK] Task created with status: processing")

        # Connect to Redis
        print("\n[4] Connecting to Redis...")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        print("    [OK] Redis connected")

        # Connect to WebSocket
        print(f"\n[5] Connecting to WebSocket: {ws_url_base}/{task_id}")
        ws_url = f"{ws_url_base}/{task_id}"

        async with websockets.connect(ws_url) as websocket:
            print("    [OK] WebSocket connected")

            # Receive initial messages
            print("\n[6] Receiving initial WebSocket messages...")
            msg1 = await websocket.recv()
            print(f"    [RX] {msg1}")

            msg2 = await websocket.recv()
            print(f"    [RX] {msg2}")

            # Define progress messages
            progress_messages = [
                {"progress": 25, "current_step": "Loading document...", "type": "progress_update"},
                {"progress": 50, "current_step": "Analyzing structure...", "type": "progress_update"},
                {"progress": 75, "current_step": "Validating fields...", "type": "progress_update"},
                {"progress": 100, "current_step": "Complete!", "type": "progress_update", "status": "completed"}
            ]

            print("\n[7] Publishing progress updates to Redis...")
            channel = f"progress:task:{task_id}"

            for i, msg in enumerate(progress_messages, 1):
                # Publish to Redis
                await redis_client.publish(channel, json.dumps(msg))
                print(f"    [{i}/4] Published to Redis: {msg['current_step']} ({msg['progress']}%)")

                # Receive via WebSocket
                try:
                    ws_msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    ws_data = json.loads(ws_msg)
                    print(f"          [RX] WebSocket: progress={ws_data.get('progress')}%, step={ws_data.get('current_step')}")

                    # Validate
                    assert ws_data.get('progress') == msg['progress'], "Progress mismatch"
                    assert ws_data.get('current_step') == msg['current_step'], "Step mismatch"

                except asyncio.TimeoutError:
                    print(f"          [ERROR] Timeout waiting for WebSocket message")
                    return False
                except AssertionError as e:
                    print(f"          [ERROR] Validation failed: {e}")
                    return False

                # Small delay
                await asyncio.sleep(0.3)

            print("\n" + "=" * 70)
            print("SUCCESS - All progress updates received correctly!")
            print("=" * 70)
            return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print("\n[8] Cleaning up...")
        try:
            # Delete test task
            if conn:
                await conn.execute("DELETE FROM dna_app.ai_tasks WHERE id = $1", task_id)
                print("    [OK] Test task deleted")
        except:
            pass

        if conn:
            await conn.close()
        if redis_client:
            await redis_client.aclose()
        print("    [OK] Connections closed")


if __name__ == "__main__":
    success = asyncio.run(test_complete_flow())
    exit(0 if success else 1)
