"""
Test WebSocket endpoint for task progress updates.

This script tests the /ws/tasks/{task_id} endpoint by:
1. Creating a test task directly in the database
2. Connecting to the WebSocket endpoint
3. Publishing test messages to Redis Pub/Sub
4. Verifying the WebSocket receives the messages
"""

import asyncio
import json
import uuid
import asyncpg
import redis.asyncio as aioredis
from websockets import connect

# Configuration
DATABASE_URL = "postgresql://dna_user:dna_password_dev@localhost:5432/dna"
REDIS_URL = "redis://localhost:6379/0"
WEBSOCKET_URL = "ws://localhost:8400/ws/tasks/{task_id}"


async def create_test_task():
    """Create a test task in the database."""
    conn = await asyncpg.connect(DATABASE_URL)
    
    task_id = str(uuid.uuid4())
    
    await conn.execute("""
        INSERT INTO dna_app.ai_tasks 
        (id, task_type, related_id, status, progress, llm_provider_id, llm_provider, llm_model, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    """, 
        task_id,
        "template:parse",
        str(uuid.uuid4()),
        "processing",
        0,
        str(uuid.uuid4()),
        "claude",
        "claude-sonnet-4-5",
        str(uuid.uuid4())
    )
    
    await conn.close()
    
    print(f"✅ Created test task: {task_id}")
    return task_id


async def test_websocket(task_id):
    """Test WebSocket connection and message forwarding."""
    print(f"\n🔌 Connecting to WebSocket: ws://localhost:8400/ws/tasks/{task_id}")
    
    try:
        async with connect(WEBSOCKET_URL.format(task_id=task_id)) as websocket:
            print("✅ WebSocket connected successfully")
            
            # Receive initial messages
            print("\n📥 Waiting for initial messages...")
            for _ in range(2):  # task_status and subscribed messages
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                print(f"📨 Received: {data['type']}")
                print(f"   {json.dumps(data, indent=2)}")
            
            # Publish test messages to Redis
            print("\n📤 Publishing test messages to Redis...")
            redis_client = await aioredis.from_url(REDIS_URL)
            
            # Message 1: Progress update
            test_message_1 = {
                "type": "progress_update",
                "task_id": task_id,
                "progress": 25,
                "current_step": "Extracting sections...",
                "eta_seconds": 30
            }
            await redis_client.publish(
                f"progress:task:{task_id}",
                json.dumps(test_message_1)
            )
            print(f"✅ Published progress update (25%)")
            
            # Wait for WebSocket to receive it
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)
            assert data['type'] == 'progress_update'
            assert data['progress'] == 25
            print(f"✅ WebSocket received progress update")
            print(f"   {json.dumps(data, indent=2)}")
            
            # Message 2: Progress update 2
            test_message_2 = {
                "type": "progress_update",
                "task_id": task_id,
                "progress": 75,
                "current_step": "Analyzing compliance...",
                "eta_seconds": 10
            }
            await redis_client.publish(
                f"progress:task:{task_id}",
                json.dumps(test_message_2)
            )
            print(f"\n✅ Published progress update (75%)")
            
            # Wait for WebSocket to receive it
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)
            assert data['type'] == 'progress_update'
            assert data['progress'] == 75
            print(f"✅ WebSocket received progress update")
            print(f"   {json.dumps(data, indent=2)}")
            
            # Message 3: Task completion
            test_message_3 = {
                "type": "task_complete",
                "task_id": task_id,
                "status": "completed",
                "result": {"success": True}
            }
            await redis_client.publish(
                f"progress:task:{task_id}",
                json.dumps(test_message_3)
            )
            print(f"\n✅ Published task completion")
            
            # Wait for WebSocket to receive it
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)
            assert data['type'] == 'task_complete'
            assert data['status'] == 'completed'
            print(f"✅ WebSocket received completion")
            print(f"   {json.dumps(data, indent=2)}")
            
            await redis_client.close()
            
            print("\n✅ All tests passed!")
            
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for WebSocket message")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def cleanup_test_task(task_id):
    """Delete test task from database."""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM dna_app.ai_tasks WHERE id = $1", task_id)
    await conn.close()
    print(f"\n🗑️  Cleaned up test task: {task_id}")


async def main():
    """Run WebSocket test."""
    print("=" * 70)
    print("WebSocket Progress Endpoint Test")
    print("=" * 70)
    
    task_id = None
    try:
        # Create test task
        task_id = await create_test_task()
        
        # Test WebSocket
        await test_websocket(task_id)
        
    finally:
        # Cleanup
        if task_id:
            await cleanup_test_task(task_id)
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
