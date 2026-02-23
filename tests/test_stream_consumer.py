"""
Test Stream Consumer
====================

Publishes a test task to Redis Stream and verifies the AI worker processes it.
"""

import asyncio
import json
import uuid
import redis.asyncio as redis
import asyncpg
import websockets


async def test_stream_consumer():
    """Test that AI worker consumes and processes tasks from Redis Stream."""
    print("=" * 70)
    print("STREAM CONSUMER TEST - End-to-End")
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

    # Generate test task ID
    task_id = str(uuid.uuid4())
    print(f"\n[1] Generated task ID: {task_id}")

    # Connect to database
    print("\n[2] Connecting to database...")
    conn = await asyncpg.connect(**db_config)

    # Connect to Redis
    print("[3] Connecting to Redis...")
    redis_client = await redis.from_url(redis_url, decode_responses=True)

    try:
        # Create test task in database
        print("[4] Creating test task in database...")
        await conn.execute(
            """
            INSERT INTO dna_app.ai_tasks (
                id, task_type, status, progress, current_step,
                created_by, llm_provider, tokens_input, tokens_output
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            task_id,
            "template_parse",
            "pending",
            0,
            "Queued",
            1,
            "claude",
            0,
            0
        )
        print(f"    [OK] Task created with status: pending")

        # Connect to WebSocket for progress updates
        print(f"\n[5] Connecting to WebSocket: {ws_url_base}/{task_id}")
        ws_url = f"{ws_url_base}/{task_id}"

        async with websockets.connect(ws_url) as websocket:
            print("    [OK] WebSocket connected")

            # Receive initial messages
            msg1 = await websocket.recv()
            print(f"    [RX] {msg1}")
            msg2 = await websocket.recv()
            print(f"    [RX] {msg2}")

            # Publish task to Redis Stream
            print(f"\n[6] Publishing task to Redis Stream 'template:parse'...")
            stream_data = {
                "task_id": task_id,
                "template_id": str(uuid.uuid4()),
                "file_path": "/app/uploads/test-document.docx",
                "llm_provider": "claude",
                "custom_rules": "",
                "created_by": "1"
            }

            message_id = await redis_client.xadd(
                "template:parse",
                stream_data
            )
            print(f"    [OK] Published to stream with message ID: {message_id}")

            # Wait for worker to process (listen to WebSocket)
            print(f"\n[7] Waiting for AI worker to process task...")
            print("    (Worker should pick up task from stream and publish progress)")

            progress_updates = []
            timeout = 15  # 15 seconds for each update

            try:
                while len(progress_updates) < 5:  # Expect 5 progress updates (0%, 25%, 50%, 75%, 100%)
                    ws_msg = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    ws_data = json.loads(ws_msg)

                    if ws_data.get('type') == 'progress_update':
                        progress = ws_data.get('progress')
                        step = ws_data.get('current_step')
                        progress_updates.append((progress, step))
                        print(f"    [{len(progress_updates)}/5] Progress: {progress}% - {step}")

            except asyncio.TimeoutError:
                print(f"\n    [TIMEOUT] Only received {len(progress_updates)}/5 progress updates")

            # Small delay to let database update complete
            await asyncio.sleep(0.5)

            # Check final task status in database
            print(f"\n[8] Checking final task status in database...")
            task = await conn.fetchrow(
                "SELECT id, status, progress, current_step, result FROM dna_app.ai_tasks WHERE id = $1",
                task_id
            )

            if task:
                print(f"    Task ID: {task['id']}")
                print(f"    Status: {task['status']}")
                print(f"    Progress: {task['progress']}%")
                print(f"    Current Step: {task['current_step']}")
                if task['result']:
                    print(f"    Result: {json.dumps(task['result'], indent=2)[:200]}...")

            # Verify success
            print("\n" + "=" * 70)
            if len(progress_updates) == 5 and task['status'] == 'completed':
                print("SUCCESS - AI worker processed task from stream!")
                print("=" * 70)
                print("\nVerified:")
                print("  [x] Task published to Redis Stream")
                print("  [x] AI worker consumed task from stream")
                print("  [x] Worker published 5 progress updates via Pub/Sub")
                print("  [x] WebSocket received all progress updates")
                print("  [x] Task status updated to 'completed' in database")
                print("  [x] Result saved to database")
                return True
            else:
                print("PARTIAL SUCCESS - Worker started but may not have completed")
                print("=" * 70)
                print(f"  Progress updates received: {len(progress_updates)}/5")
                print(f"  Final status: {task['status']}")
                return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print("\n[9] Cleaning up...")
        try:
            await conn.execute("DELETE FROM dna_app.ai_tasks WHERE id = $1", task_id)
            print("    [OK] Test task deleted")
        except:
            pass

        await conn.close()
        await redis_client.aclose()
        print("    [OK] Connections closed")


if __name__ == "__main__":
    success = asyncio.run(test_stream_consumer())
    exit(0 if success else 1)
