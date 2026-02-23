"""
End-to-End Integration Test
============================

Tests the complete DNA workflow from document upload to parsed template.

Workflow:
1. Upload Word document (sample ISO 9001)
2. Create task in database
3. Publish to Redis Stream
4. AI worker consumes task
5. Parser agent processes with Claude
6. Progress updates via Pub/Sub → WebSocket
7. Result saved to database
8. Verify template structure, fields, metadata
"""

import asyncio
import json
import uuid
import time
import shutil
from pathlib import Path

import websockets
import redis.asyncio as redis
import asyncpg


async def test_full_workflow():
    """Test complete end-to-end workflow with real ISO document."""
    print("=" * 80)
    print("END-TO-END INTEGRATION TEST - Full DNA Workflow")
    print("=" * 80)

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

    # Paths
    sample_doc = Path("tests/fixtures/sample_iso9001_qms_template.docx")
    # Use shared volume path accessible to AI service
    upload_path = Path("ai-service/uploads/dna_test_upload.docx")

    if not sample_doc.exists():
        print(f"\n[ERROR] Sample document not found: {sample_doc}")
        print("Run: python tests/fixtures/create_sample_iso_document.py")
        return False

    # Generate test IDs
    task_id = str(uuid.uuid4())
    template_id = str(uuid.uuid4())

    print(f"\n[1] Test Setup")
    print(f"    Task ID: {task_id}")
    print(f"    Template ID: {template_id}")
    print(f"    Document: {sample_doc}")

    # Copy sample document to upload location (simulating upload)
    print(f"\n[2] Simulating document upload...")
    shutil.copy(sample_doc, upload_path)
    print(f"    [OK] Document copied to: {upload_path}")

    # Connect to services
    print(f"\n[3] Connecting to services...")
    conn = await asyncpg.connect(**db_config)
    print(f"    [OK] Database connected")

    redis_client = await redis.from_url(redis_url, decode_responses=True)
    print(f"    [OK] Redis connected")

    try:
        # Create task in database
        print(f"\n[4] Creating task in database...")
        await conn.execute(
            """
            INSERT INTO dna_app.ai_tasks (
                id, task_type, related_id, status, progress, current_step,
                created_by, llm_provider, tokens_input, tokens_output
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            task_id,
            "template_parse",
            template_id,
            "pending",
            0,
            "Queued",
            1,  # User ID
            "claude",
            0,
            0
        )
        print(f"    [OK] Task created (status: pending)")

        # Connect to WebSocket
        print(f"\n[5] Connecting to WebSocket for real-time updates...")
        ws_url = f"{ws_url_base}/{task_id}"

        async with websockets.connect(ws_url) as websocket:
            print(f"    [OK] WebSocket connected: {ws_url}")

            # Receive initial messages
            msg1 = json.loads(await websocket.recv())
            print(f"    [RX] {msg1['type']}: status={msg1['status']}")

            msg2 = json.loads(await websocket.recv())
            print(f"    [RX] {msg2['type']}: subscribed to {msg2['channel']}")

            # Publish task to Redis Stream
            print(f"\n[6] Publishing task to Redis Stream...")
            stream_data = {
                "task_id": task_id,
                "template_id": template_id,
                "file_path": "/app/uploads/dna_test_upload.docx",  # Path as seen by AI service container
                "iso_standard": "ISO 9001:2015",
                "custom_rules": "",
                "created_by": "1"
            }

            message_id = await redis_client.xadd("template:parse", stream_data)
            print(f"    [OK] Task published to stream: {message_id}")

            # Monitor progress via WebSocket
            print(f"\n[7] Monitoring AI worker progress...")
            progress_updates = []
            milestones = []
            completion_data = None
            start_time = time.time()

            timeout = 60  # 60 seconds timeout
            last_progress = 0

            try:
                while True:
                    ws_msg = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    data = json.loads(ws_msg)

                    msg_type = data.get('type')

                    if msg_type == 'progress_update':
                        progress = data.get('progress', 0)
                        step = data.get('current_step', '')
                        eta = data.get('eta_message', '')
                        elapsed = data.get('elapsed_seconds', 0)

                        progress_updates.append(data)

                        # Only print significant progress changes
                        if progress > last_progress + 5 or progress in [0, 100]:
                            print(f"    [{progress:3d}%] {step}")
                            if eta:
                                print(f"          ({eta}, elapsed: {elapsed}s)")
                            last_progress = progress

                    elif msg_type == 'milestone':
                        milestone = data.get('milestone')
                        milestones.append(data)
                        print(f"    [MILESTONE] {milestone}")

                    elif msg_type == 'task_complete':
                        completion_data = data
                        print(f"    [100%] {data.get('current_step')}")
                        print(f"          Total time: {data.get('elapsed_seconds')}s")
                        break

                    elif msg_type == 'task_error':
                        error = data.get('error')
                        error_type = data.get('error_type')
                        print(f"    [ERROR] {error_type}: {error}")
                        return False

            except asyncio.TimeoutError:
                print(f"    [TIMEOUT] Waited {timeout}s, worker may be slow or stuck")
                return False

            total_time = int(time.time() - start_time)

            # Verify task in database
            print(f"\n[8] Verifying task in database...")
            task = await conn.fetchrow(
                """
                SELECT
                    id, status, progress, current_step, result,
                    cost_usd, tokens_input, tokens_output, duration_seconds
                FROM dna_app.ai_tasks
                WHERE id = $1
                """,
                task_id
            )

            if not task:
                print(f"    [ERROR] Task not found in database")
                return False

            print(f"    Task Status: {task['status']}")
            print(f"    Progress: {task['progress']}%")
            print(f"    Duration: {task['duration_seconds']}s")
            print(f"    Cost: ${task['cost_usd']}")
            print(f"    Tokens: {task['tokens_input']} in, {task['tokens_output']} out")

            if task['status'] != 'completed':
                print(f"    [ERROR] Expected status 'completed', got '{task['status']}'")
                return False

            # Parse result
            result = task['result']
            if isinstance(result, str):
                result = json.loads(result)

            # Validate result structure
            print(f"\n[9] Validating parsed template...")

            required_keys = ['template_type', 'iso_standard', 'sections', 'fields', 'metadata']
            for key in required_keys:
                if key not in result:
                    print(f"    [ERROR] Missing key in result: {key}")
                    return False

            sections = result['sections']
            fields = result['fields']
            metadata = result['metadata']

            print(f"    [OK] Template Type: {result['template_type']}")
            print(f"    [OK] ISO Standard: {result['iso_standard']}")
            print(f"    [OK] Sections: {len(sections)} ({metadata['total_sections']} expected)")
            print(f"    [OK] Fields: {len(fields)} ({metadata['total_fields']} expected)")
            print(f"    [OK] Required Fields: {metadata['required_fields']}")
            print(f"    [OK] Completion Estimate: {metadata['completion_estimate_minutes']} minutes")

            # Validate sections
            print(f"\n[10] Validating sections...")
            if len(sections) < 3:
                print(f"    [WARN] Expected at least 3 sections, found {len(sections)}")

            for i, section in enumerate(sections[:3], 1):
                print(f"    Section {i}: {section.get('title', 'Untitled')}")
                print(f"      - ID: {section.get('id')}")
                print(f"      - Level: {section.get('level')}")
                print(f"      - Has Fields: {section.get('has_fields', False)}")

            # Validate fields
            print(f"\n[11] Validating fields...")
            if len(fields) < 10:
                print(f"    [WARN] Expected at least 10 fields, found {len(fields)}")

            field_types = {}
            for field in fields:
                field_type = field.get('type', 'unknown')
                field_types[field_type] = field_types.get(field_type, 0) + 1

            print(f"    Field Types Distribution:")
            for field_type, count in sorted(field_types.items()):
                print(f"      - {field_type}: {count}")

            # Show sample fields
            print(f"\n    Sample Fields:")
            for i, field in enumerate(fields[:5], 1):
                print(f"      {i}. {field.get('label', 'Unlabeled')}")
                print(f"         Type: {field.get('type')}, Required: {field.get('required', False)}")

            # Final validation
            print(f"\n[12] Final Validation...")
            validations = {
                "Task completed": task['status'] == 'completed',
                "Result has sections": len(sections) > 0,
                "Result has fields": len(fields) > 0,
                "Progress updates received": len(progress_updates) >= 3,
                "WebSocket working": True,
                "Database updated": True,
                "Cost tracked": task['cost_usd'] is not None,
                "Tokens tracked": task['tokens_input'] > 0
            }

            all_passed = all(validations.values())

            for check, passed in validations.items():
                status = "[OK]" if passed else "[FAIL]"
                print(f"    {status} {check}")

            # Summary
            print("\n" + "=" * 80)
            if all_passed:
                print("SUCCESS - End-to-End Test Passed!")
                print("=" * 80)
                print(f"\n  Workflow:")
                print(f"    1. Document uploaded: sample_iso9001_qms_template.docx")
                print(f"    2. Task created in database")
                print(f"    3. Published to Redis Stream: template:parse")
                print(f"    4. AI worker consumed task")
                print(f"    5. Parser agent analyzed with Claude AI")
                print(f"    6. {len(progress_updates)} progress updates via WebSocket")
                print(f"    7. Result saved to database")
                print(f"    8. Template ready: {len(sections)} sections, {len(fields)} fields")
                print(f"\n  Performance:")
                print(f"    Total time: {total_time}s")
                print(f"    Processing time: {task['duration_seconds']}s")
                print(f"    Cost: ${task['cost_usd']}")
                print(f"    Tokens: {task['tokens_input']} + {task['tokens_output']} = {task['tokens_input'] + task['tokens_output']}")
                print(f"\n  User Experience:")
                print(f"    Estimated completion time: {metadata['completion_estimate_minutes']} minutes")
                print(f"    Required fields: {metadata['required_fields']}/{metadata['total_fields']}")
                return True
            else:
                print("FAILED - Some validations did not pass")
                print("=" * 80)
                return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print(f"\n[13] Cleaning up...")
        try:
            await conn.execute("DELETE FROM dna_app.ai_tasks WHERE id = $1", task_id)
            print(f"    [OK] Test task deleted from database")
        except:
            pass

        try:
            upload_path.unlink()
            print(f"    [OK] Uploaded file deleted")
        except:
            pass

        await conn.close()
        await redis_client.aclose()
        print(f"    [OK] Connections closed")


if __name__ == "__main__":
    success = asyncio.run(test_full_workflow())
    exit(0 if success else 1)
