"""
Redis Stream Consumer
=====================

Consumes tasks from Redis Streams and processes them.
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import time

from redis_client import redis_client
from db_client import db_client
from config import settings
from agents.template import TemplateAgent
from agents.iso_builder import ISOBuilderAgent
from progress_publisher import progress_publisher
from telemetry import telemetry, generate_trace_id
from health_publisher import publish_healthy, publish_error

logger = logging.getLogger(__name__)


class StreamConsumer:
    """Redis Stream consumer for AI tasks."""

    def __init__(self):
        self.consumer_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.tasks: Dict[str, asyncio.Task] = {}
        self.template_agent: Optional[TemplateAgent] = None
        self.iso_builder_agent: Optional[ISOBuilderAgent] = None

    async def start(self):
        """Start consuming from streams."""
        logger.info(f"Starting stream consumer: {self.consumer_id}")

        # Connect to Redis and Database
        await redis_client.connect()
        await db_client.connect()

        # Test connections
        if await redis_client.ping():
            logger.info("✓ Redis connection verified")
            await publish_healthy("redis", "AI worker connected to Redis successfully")
        else:
            await publish_error("redis", "AI worker Redis connection failed")
            raise RuntimeError("Redis connection failed")

        # Verify database connection
        try:
            async with db_client._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("✓ Database connection verified")
            await publish_healthy("database", "AI worker connected to database successfully")
        except Exception as e:
            await publish_error("database", f"AI worker database connection failed: {e}")
            raise

        # Create consumer groups
        await self._create_consumer_groups()

        # Read provider/model from DB (admin UI can override env vars)
        provider = settings.LLM_PROVIDER
        active_model = None
        try:
            async with db_client._pool.acquire() as conn:
                cfg = await conn.fetchrow(
                    f"SELECT provider, model"
                    f" FROM {settings.DATABASE_APP_SCHEMA}.ai_config WHERE service = 'iso_builder'"
                )
            if cfg:
                provider = cfg["provider"] or provider
                active_model = cfg["model"]
            logger.info(f"AI config from DB: provider={provider}, model={active_model}")
        except Exception as e:
            logger.warning(f"Could not read ai_config from DB, using env vars: {e}")

        # Resolve API key from central llm_providers table
        api_key, model = None, None
        try:
            async with db_client._pool.acquire() as conn:
                prov_row = await conn.fetchrow(
                    f"SELECT api_key FROM {settings.DATABASE_APP_SCHEMA}.llm_providers"
                    f" WHERE name = $1 AND enabled = true",
                    provider,
                )
            if prov_row and prov_row["api_key"]:
                raw = prov_row["api_key"]
                if raw.startswith("enc:"):
                    import base64, hashlib
                    from cryptography.fernet import Fernet
                    fkey = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
                    api_key = Fernet(fkey).decrypt(raw[4:].encode()).decode()
                else:
                    api_key = raw
                model = active_model
        except Exception as e:
            logger.warning(f"Could not read API key from llm_providers: {e} — falling back to env")

        # Fallback to env vars if DB key not set
        if not api_key:
            if provider == "gemini":
                api_key = settings.GOOGLE_API_KEY
                model = model or settings.GEMINI_MODEL
            elif provider == "anthropic":
                api_key = settings.ANTHROPIC_API_KEY
                model = model or settings.ANTHROPIC_MODEL
            elif provider == "groq":
                api_key = settings.GROQ_API_KEY
                model = model or settings.GROQ_MODEL

        if api_key:
            self.template_agent = TemplateAgent(
                api_key=api_key, model=model, max_tokens=16384, provider=provider
            )
            self.iso_builder_agent = ISOBuilderAgent(
                api_key=api_key, model=model, max_tokens=64000, provider=provider
            )
            logger.info(f"✓ Agents initialized (provider={provider}, model={model})")
        else:
            logger.warning(f"API key not set for provider={provider} — agents not initialized")

        self.running = True
        logger.info("Stream consumer started")

    async def stop(self):
        """Stop consuming and cleanup."""
        logger.info("Stopping stream consumer...")
        self.running = False

        # Cancel all running tasks
        for task_id, task in self.tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Cancelled task {task_id}")

        # Disconnect clients
        await redis_client.disconnect()
        await db_client.disconnect()

        logger.info("Stream consumer stopped")

    async def _create_consumer_groups(self):
        """Create consumer groups for all streams."""
        streams = [
            ("template:parse", "parser-workers"),
            ("template:edit", "editor-workers"),
            ("template:review", "reviewer-workers"),
            ("iso:build", "iso-builder-workers"),
            ("ai:iso360_template",   "ai-iso360-template-workers"),
            ("ai:iso360_adjustment", "ai-iso360-adjustment-workers"),
            ("ai:iso360_kyc",        "ai-iso360-kyc-workers"),
        ]

        for stream_name, group_name in streams:
            await redis_client.create_consumer_group(
                stream_name,
                group_name,
                start_id="0"  # Process from beginning on first run
            )

    async def consume_forever(self):
        """Main consumer loop - reads from all streams."""
        logger.info("Starting infinite consumer loop...")

        while self.running:
            try:
                # Read from template:parse stream
                await self._consume_stream(
                    stream_name="template:parse",
                    group_name="parser-workers",
                    handler=self._handle_parse_task
                )

                # Read from template:edit stream
                await self._consume_stream(
                    stream_name="template:edit",
                    group_name="editor-workers",
                    handler=self._handle_edit_task
                )

                # Read from iso:build stream
                await self._consume_stream(
                    stream_name="iso:build",
                    group_name="iso-builder-workers",
                    handler=self._handle_iso_build_task
                )

                # Read from ai:iso360_template stream
                await self._consume_stream(
                    stream_name="ai:iso360_template",
                    group_name="ai-iso360-template-workers",
                    handler=self._handle_iso360_template_job
                )

                # Read from ai:iso360_adjustment stream
                await self._consume_stream(
                    stream_name="ai:iso360_adjustment",
                    group_name="ai-iso360-adjustment-workers",
                    handler=self._handle_iso360_adjustment_job
                )

                # Read from ai:iso360_kyc stream
                await self._consume_stream(
                    stream_name="ai:iso360_kyc",
                    group_name="ai-iso360-kyc-workers",
                    handler=self._handle_iso360_kyc_job
                )

                # TODO: Add template:review stream when reviewer agent is implemented
                # await self._consume_stream(
                #     stream_name="template:review",
                #     group_name="reviewer-workers",
                #     handler=self._handle_review_task
                # )

                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                logger.info("Consumer loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _consume_stream(
        self,
        stream_name: str,
        group_name: str,
        handler
    ):
        """
        Consume messages from a specific stream.

        Args:
            stream_name: Name of the stream
            group_name: Consumer group name
            handler: Async function to handle each message
        """
        try:
            # Read messages (block for 5 seconds)
            messages = await redis_client.read_stream_group(
                stream_name=stream_name,
                group_name=group_name,
                consumer_name=self.consumer_id,
                count=1,
                block=5000
            )

            if not messages:
                return

            # Process each message
            for stream, message_list in messages:
                for message_id, message_data in message_list:
                    await self._process_message(
                        stream_name=stream_name,
                        group_name=group_name,
                        message_id=message_id,
                        message_data=message_data,
                        handler=handler
                    )

        except Exception as e:
            logger.error(f"Error consuming from {stream_name}: {e}")

    async def _process_message(
        self,
        stream_name: str,
        group_name: str,
        message_id: str,
        message_data: Dict[str, str],
        handler
    ):
        """
        Process a single message from the stream.

        Args:
            stream_name: Name of the stream
            group_name: Consumer group name
            message_id: Redis message ID
            message_data: Message payload
            handler: Async function to handle the message
        """
        logger.info(f"[{self.consumer_id}] Received message {message_id} from {stream_name}")
        logger.debug(f"Message data: {message_data}")

        try:
            # Parse message data (Redis returns strings, may need JSON parsing)
            parsed_data = {}
            for key, value in message_data.items():
                try:
                    # Try to parse as JSON if it looks like JSON
                    if value.startswith('{') or value.startswith('[') or value.startswith('"'):
                        parsed_data[key] = json.loads(value)
                    else:
                        parsed_data[key] = value
                except json.JSONDecodeError:
                    parsed_data[key] = value

            # Call the handler
            await handler(parsed_data)

            # Acknowledge message
            await redis_client.ack_message(stream_name, group_name, message_id)
            logger.info(f"[{self.consumer_id}] Completed message {message_id}")

        except Exception as e:
            logger.error(f"[{self.consumer_id}] Failed to process message {message_id}: {e}")
            # Don't ACK on error - message will be redelivered
            # TODO: Implement dead letter queue for failed messages

    async def _handle_parse_task(self, data: Dict[str, Any]):
        """
        Handle template parsing task.

        Args:
            data: Task data from stream
                - task_id: UUID
                - template_id: UUID
                - file_path: Path to Word document
                - llm_provider: LLM provider name (e.g., 'claude')
                - custom_rules: Optional custom parsing rules
                - iso_standard: Optional ISO standard
                - created_by: User ID
                - trace_id: Optional trace ID (generated if missing)
        """
        task_id = data.get('task_id')
        template_file_id = data.get('template_file_id')  # Reference file UUID
        file_path = data.get('file_path')
        custom_rules = data.get('custom_rules', '')
        iso_standard = data.get('iso_standard', 'ISO 9001:2015')
        user_id = data.get('created_by')

        # Extract or generate trace_id for operation tracking
        trace_id = data.get('trace_id', generate_trace_id())

        # Extract file name for user-friendly display
        file_name = file_path.split('/')[-1] if file_path else 'document.docx'

        logger.info(f"Processing parse task: {task_id}")
        logger.info(f"  File: {file_path}")
        logger.info(f"  ISO Standard: {iso_standard}")

        # Telemetry: Operation started
        telemetry.operation_started(
            operation_name=f"Parse Template: {file_name}",
            trace_id=trace_id,
            task_id=task_id,
            user_id=user_id,
            file_name=file_name,
            iso_standard=iso_standard,
            has_custom_rules=bool(custom_rules)
        )

        start_time = time.time()
        tokens_used = {"input": 0, "output": 0}

        try:
            # Update task status to processing
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=0,
                current_step='Initializing parser...'
            )

            # Publish initial progress
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=0,
                current_step="Initializing parser...",
                details={"iso_standard": iso_standard}
            )

            # Check if template agent is available
            if not self.template_agent:
                raise RuntimeError("Template agent not initialized (missing ANTHROPIC_API_KEY)")

            # Progress: 10% - Ready to parse
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=10,
                current_step="Starting document analysis..."
            )
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=10,
                current_step='Starting document analysis...'
            )

            # Define progress callback for template agent
            async def on_progress(progress: int, step: str):
                """Forward progress updates from template agent"""
                await progress_publisher.publish_progress(
                    task_id=task_id,
                    progress=progress,
                    current_step=step
                )
                await db_client.update_task_status(
                    task_id=task_id,
                    status='processing',
                    progress=progress,
                    current_step=step
                )

            # ACTUAL PARSING with AI (template agent reports progress internally)
            logger.info(f"Task {task_id}: Calling template agent...")
            template = await self.template_agent.parse_document(
                file_path=file_path,
                custom_rules=custom_rules if custom_rules else None,
                iso_standard=iso_standard,
                trace_id=trace_id,
                task_id=task_id,
                progress_callback=on_progress
            )

            # Calculate metrics
            duration = int(time.time() - start_time)

            # Estimate tokens (we'll track actual tokens in future)
            # For now, rough estimate based on template size
            tokens_used["input"] = len(str(template)) // 4  # Rough estimate
            tokens_used["output"] = len(json.dumps(template)) // 4

            # Estimate cost (Claude Sonnet 4.5: $3/M input, $15/M output)
            cost = (tokens_used["input"] / 1_000_000 * 3.0) + \
                   (tokens_used["output"] / 1_000_000 * 15.0)

            # Progress: 100% - Save result to database FIRST
            await db_client.save_task_result(
                task_id=task_id,
                result=template,
                cost_usd=round(cost, 4),
                tokens_input=tokens_used["input"],
                tokens_output=tokens_used["output"],
                duration_seconds=duration
            )

            # Create template entry (CORRECT APPROACH)
            try:
                template_id = await db_client.create_template(
                    name=template.get('document_title', template.get('name', 'Untitled Template')),
                    description=f"Generated from {file_name}",
                    template_file_id=template_file_id,
                    template_structure=template,
                    ai_task_id=task_id,
                    iso_standard=template.get('iso_standard')
                )
                logger.info(f"Created template {template_id} for task {task_id}")
            except Exception as e:
                logger.error(f"Failed to create template for task {task_id}: {e}")
                # Don't fail the entire task if template creation fails

            # Then publish completion (ensures DB is updated when clients receive this)
            metadata = template.get('metadata', {})
            result_summary = {
                "fixed_sections": metadata.get('total_fixed_sections', 0),
                "fillable_sections": metadata.get('total_fillable_sections', 0),
                "completion_estimate_minutes": metadata.get('completion_estimate_minutes', 0),
                "semantic_tags": metadata.get('semantic_tags_used', []),
                "cost_usd": round(cost, 4),
                "duration_seconds": duration,
                "llm_provider": self.template_agent.provider if self.template_agent else "unknown",
                "llm_model": self.template_agent.model if self.template_agent else "unknown"
            }

            await progress_publisher.publish_completion(
                task_id=task_id,
                result_summary=result_summary
            )

            # Telemetry: Operation completed
            telemetry.operation_completed(
                operation_name=f"Parse Template: {file_name}",
                trace_id=trace_id,
                task_id=task_id,
                duration_seconds=duration,
                result_summary=result_summary
            )

            logger.info(f"Task {task_id}: Completed successfully")
            logger.info(f"  Duration: {duration}s")
            logger.info(f"  Cost: ${cost:.4f}")
            logger.info(f"  Fixed sections: {template['metadata']['total_fixed_sections']}")
            logger.info(f"  Fillable sections: {template['metadata']['total_fillable_sections']}")
            logger.info(f"  Semantic tags: {template['metadata']['semantic_tags_used']}")

        except FileNotFoundError as e:
            logger.error(f"Task {task_id}: File not found - {e}")
            telemetry.operation_failed(
                operation_name=f"Parse Template: {file_name}",
                trace_id=trace_id,
                task_id=task_id,
                error=f"Document not found at {file_path}",
                error_type="file_not_found"
            )
            await self._handle_task_error(
                task_id=task_id,
                error=f"Document not found at {file_path}",
                error_type="file_not_found",
                recoverable=False
            )

        except RuntimeError as e:
            logger.error(f"Task {task_id}: Runtime error - {e}")
            telemetry.operation_failed(
                operation_name=f"Parse Template: {file_name}",
                trace_id=trace_id,
                task_id=task_id,
                error=str(e),
                error_type="configuration_error"
            )
            await self._handle_task_error(
                task_id=task_id,
                error=str(e),
                error_type="configuration_error",
                recoverable=False
            )

        except Exception as e:
            logger.error(f"Task {task_id}: Unexpected error - {e}")
            import traceback
            traceback.print_exc()
            telemetry.operation_failed(
                operation_name=f"Parse Template: {file_name}",
                trace_id=trace_id,
                task_id=task_id,
                error=f"Parsing failed: {str(e)}",
                error_type="parsing_error"
            )
            await self._handle_task_error(
                task_id=task_id,
                error=f"Parsing failed: {str(e)}",
                error_type="parsing_error",
                recoverable=True
            )

    async def _handle_task_error(
        self,
        task_id: str,
        error: str,
        error_type: str = "parsing_error",
        recoverable: bool = False
    ):
        """Helper to handle task errors with enhanced messaging."""
        # Update task as failed
        await db_client.update_task_status(
            task_id=task_id,
            status='failed',
            error=error
        )

        # Publish error with helpful details
        await progress_publisher.publish_error(
            task_id=task_id,
            error_message=error,
            error_type=error_type,
            recoverable=recoverable
        )

    async def _handle_edit_task(self, data: Dict[str, Any]):
        """
        Handle template editing task.

        Args:
            data: Task data from stream
                - task_id: UUID
                - template_id: UUID of template to edit
                - instructions: Natural language editing instructions
                - created_by: User ID
                - trace_id: Optional trace ID (generated if missing)
        """
        task_id = data.get('task_id')
        template_id = data.get('template_id')
        instructions = data.get('instructions', '')
        user_id = data.get('created_by')

        # Extract or generate trace_id for operation tracking
        trace_id = data.get('trace_id', generate_trace_id())

        logger.info(f"Processing edit task: {task_id}")
        logger.info(f"  Template ID: {template_id}")
        logger.info(f"  Instructions: {instructions[:100]}...")

        # Telemetry: Operation started
        telemetry.operation_started(
            operation_name=f"Edit Template: {template_id}",
            trace_id=trace_id,
            task_id=task_id,
            user_id=user_id,
            template_id=template_id,
            instructions_length=len(instructions)
        )

        start_time = time.time()

        try:
            # Update task status to processing
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=0,
                current_step='Initializing editor...'
            )

            # Publish initial progress
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=0,
                current_step="Initializing editor...",
                details={"template_id": template_id}
            )

            # Check if template agent is available
            if not self.template_agent:
                raise RuntimeError("Template agent not initialized (missing ANTHROPIC_API_KEY)")

            # Progress: 20% - Loading template
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=20,
                current_step="Loading template from database..."
            )
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=20,
                current_step='Loading template from database...'
            )

            # Fetch existing template from database
            existing_template = await db_client.get_template(template_id)
            if not existing_template:
                raise ValueError(f"Template not found: {template_id}")

            # Progress: 40% - Analyzing instructions
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=40,
                current_step="Analyzing editing instructions with Claude AI..."
            )
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=40,
                current_step='Analyzing editing instructions with Claude...'
            )

            # Progress: 70% - Applying changes
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=70,
                current_step="Applying changes to template..."
            )
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=70,
                current_step='Applying changes to template...'
            )

            # ACTUAL EDITING with Claude
            logger.info(f"Task {task_id}: Calling template agent for editing...")
            edited_template = await self.template_agent.edit_template(
                template=existing_template,
                instructions=instructions,
                trace_id=trace_id,
                task_id=task_id
            )

            # Progress: 90% - Validating
            await progress_publisher.publish_progress(
                task_id=task_id,
                progress=90,
                current_step="Validating edited template..."
            )
            await db_client.update_task_status(
                task_id=task_id,
                status='processing',
                progress=90,
                current_step='Validating edited template...'
            )

            # Calculate metrics
            duration = int(time.time() - start_time)

            # Estimate tokens and cost
            tokens_used_input = len(json.dumps(existing_template)) // 4 + len(instructions) // 4
            tokens_used_output = len(json.dumps(edited_template)) // 4
            cost = (tokens_used_input / 1_000_000 * 3.0) + (tokens_used_output / 1_000_000 * 15.0)

            # Progress: 100% - Save result to database
            await db_client.save_task_result(
                task_id=task_id,
                result=edited_template,
                cost_usd=round(cost, 4),
                tokens_input=tokens_used_input,
                tokens_output=tokens_used_output,
                duration_seconds=duration
            )

            # Publish completion
            metadata = edited_template.get('metadata', {})
            result_summary = {
                "fixed_sections": metadata.get('total_fixed_sections', 0),
                "fillable_sections": metadata.get('total_fillable_sections', 0),
                "semantic_tags": metadata.get('semantic_tags_used', []),
                "cost_usd": round(cost, 4),
                "duration_seconds": duration,
                "changes_applied": True
            }

            await progress_publisher.publish_completion(
                task_id=task_id,
                result_summary=result_summary
            )

            # Telemetry: Operation completed
            telemetry.operation_completed(
                operation_name=f"Edit Template: {template_id}",
                trace_id=trace_id,
                task_id=task_id,
                duration_seconds=duration,
                result_summary=result_summary
            )

            logger.info(f"Task {task_id}: Edit completed successfully")
            logger.info(f"  Duration: {duration}s")
            logger.info(f"  Cost: ${cost:.4f}")

        except ValueError as e:
            logger.error(f"Task {task_id}: Template not found - {e}")
            telemetry.operation_failed(
                operation_name=f"Edit Template: {template_id}",
                trace_id=trace_id,
                task_id=task_id,
                error=str(e),
                error_type="template_not_found"
            )
            await self._handle_task_error(
                task_id=task_id,
                error=str(e),
                error_type="template_not_found",
                recoverable=False
            )

        except RuntimeError as e:
            logger.error(f"Task {task_id}: Runtime error - {e}")
            telemetry.operation_failed(
                operation_name=f"Edit Template: {template_id}",
                trace_id=trace_id,
                task_id=task_id,
                error=str(e),
                error_type="configuration_error"
            )
            await self._handle_task_error(
                task_id=task_id,
                error=str(e),
                error_type="configuration_error",
                recoverable=False
            )

        except Exception as e:
            logger.error(f"Task {task_id}: Unexpected error - {e}")
            import traceback
            traceback.print_exc()
            telemetry.operation_failed(
                operation_name=f"Edit Template: {template_id}",
                trace_id=trace_id,
                task_id=task_id,
                error=f"Editing failed: {str(e)}",
                error_type="editing_error"
            )
            await self._handle_task_error(
                task_id=task_id,
                error=f"Editing failed: {str(e)}",
                error_type="editing_error",
                recoverable=True
            )

    async def _handle_iso_build_task(self, data: Dict[str, Any]):
        """
        Handle ISO build task from iso:build stream.
        Reads ISO PDF, calls ISOBuilderAgent, saves ISO standard + templates to DB.
        Uses per-task provider/model if provided in message, else falls back to global agent.
        """
        task_id = data.get('task_id')
        file_path = data.get('file_path')
        original_filename = data.get('original_filename', '')
        iso_code = data.get('iso_code')
        iso_name = data.get('iso_name')
        iso_description = data.get('iso_description', '')
        iso_color = data.get('iso_color', '#8b5cf6')
        iso_language = data.get('iso_language', 'en')
        template_format = data.get('template_format', 'legacy')
        created_by = data.get('created_by')
        trace_id = data.get('trace_id', generate_trace_id())
        # Per-task provider/model override
        task_provider = data.get('ai_provider')
        task_model = data.get('ai_model')

        logger.info(f"Processing ISO build task: {task_id} for {iso_code}")
        import time as _time
        task_start = _time.time()

        # Resolve agent for this task
        iso_agent = self.iso_builder_agent
        if task_provider and task_model:
            api_key = None
            # Read key from DB first, fall back to env vars
            try:
                async with db_client._pool.acquire() as conn:
                    prow = await conn.fetchrow(
                        f"SELECT api_key FROM {settings.DATABASE_APP_SCHEMA}.llm_providers"
                        f" WHERE name = $1 AND enabled = true",
                        task_provider,
                    )
                if prow and prow["api_key"]:
                    raw = prow["api_key"]
                    if raw.startswith("enc:"):
                        import base64 as _b64, hashlib as _hs
                        from cryptography.fernet import Fernet as _F
                        fk = _b64.urlsafe_b64encode(_hs.sha256(settings.SECRET_KEY.encode()).digest())
                        api_key = _F(fk).decrypt(raw[4:].encode()).decode()
                    else:
                        api_key = raw
            except Exception as _e:
                logger.warning(f"Per-task DB key lookup failed: {_e}")
            if not api_key:
                if task_provider == "gemini":
                    api_key = settings.GOOGLE_API_KEY
                elif task_provider == "anthropic":
                    api_key = settings.ANTHROPIC_API_KEY
                elif task_provider == "groq":
                    api_key = settings.GROQ_API_KEY
            if api_key:
                iso_agent = ISOBuilderAgent(
                    api_key=api_key, model=task_model, max_tokens=64000, provider=task_provider
                )
                logger.info(f"Task {task_id}: using per-task agent (provider={task_provider}, model={task_model})")

        effective_provider = task_provider or (iso_agent.provider if iso_agent else "unknown")
        effective_model = task_model or (iso_agent.model if iso_agent else "unknown")

        try:
            await db_client.update_task_status(task_id=task_id, status='processing', progress=5, current_step='Starting ISO build...')
            await progress_publisher.publish_progress(task_id=task_id, progress=5, current_step="Starting ISO build...")

            if not iso_agent:
                raise RuntimeError("ISO builder agent not initialized (missing API key)")

            # Load prompt from DB — key depends on chosen format
            prompt_key = 'iso_build_formal' if template_format == 'formal' else 'iso_build'
            async with db_client._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT prompt_text FROM {settings.DATABASE_APP_SCHEMA}.ai_prompts WHERE prompt_key = $1 AND is_active = true",
                    prompt_key
                )
            if not row:
                raise RuntimeError(f"{prompt_key} prompt not found in ai_prompts table.")
            prompt_template = row['prompt_text']
            async with db_client._pool.acquire() as conn2:
                provider_row = await conn2.fetchrow(
                    f"SELECT send_as_strategy FROM {settings.DATABASE_APP_SCHEMA}.llm_providers WHERE name = $1",
                    effective_provider
                )
            send_as_strategy = provider_row['send_as_strategy'] if provider_row else 'extract_text'
            logger.info(f"Task {task_id}: send_as_strategy={send_as_strategy}")

            async def on_progress(progress: int, step: str):
                await progress_publisher.publish_progress(task_id=task_id, progress=progress, current_step=step)
                await db_client.update_task_status(task_id=task_id, status='processing', progress=progress, current_step=step)

            result = await iso_agent.build_from_pdf(
                pdf_path=file_path,
                prompt_template=prompt_template,
                language=iso_language,
                send_as_strategy=send_as_strategy,
                trace_id=trace_id,
                task_id=task_id,
                progress_callback=on_progress,
            )

            duration_ms = int((_time.time() - task_start) * 1000)

            await on_progress(85, "Saving ISO standard to database...")

            summary = result.get('summary', {})
            placeholder_dictionary = result.get('placeholder_dictionary', [])
            templates = result.get('templates', [])

            import json as _json
            ai_metadata = {
                "standard_name": summary.get('standard_name', iso_name),
                "overview": summary.get('overview', ''),
                "total_clauses": summary.get('total_clauses', 0),
                "total_controls": summary.get('total_controls', 0),
                "key_themes": summary.get('key_themes', []),
                "document_count": summary.get('document_count', len(templates)),
                "language": iso_language,
                "built_by_ai": True,
                "model": effective_model,
                "cost_usd": result.get('cost_usd', 0),
                "source_pdf_filename": original_filename,
            }
            requirements_summary = summary.get('overview', '') or ', '.join(summary.get('key_themes', []))

            async with db_client._pool.acquire() as conn:
                iso_row = await conn.fetchrow(
                    f"""
                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.iso_standards
                        (code, name, description, requirements_summary, color, ai_metadata, tags, language, active, display_order)
                    VALUES ($1, $2, $3, $4, $5, $6::JSONB, $7, $8, true, 99)
                    RETURNING id
                    """,
                    iso_code, iso_name,
                    iso_description or summary.get('overview', ''),
                    requirements_summary, iso_color,
                    _json.dumps(ai_metadata),
                    summary.get('key_themes', []),
                    iso_language,
                )
                iso_standard_id = str(iso_row['id'])

                # Save placeholder_dictionary to iso_standards
                if placeholder_dictionary:
                    await conn.execute(
                        f"UPDATE {settings.DATABASE_APP_SCHEMA}.iso_standards "
                        f"SET placeholder_dictionary = $1::JSONB WHERE id = $2",
                        _json.dumps(placeholder_dictionary), iso_row['id']
                    )

                # Save iso-level cross-cutting recurring activities
                iso_recurring = result.get('iso_recurring_activities', [])
                if iso_recurring:
                    await conn.execute(
                        f"UPDATE {settings.DATABASE_APP_SCHEMA}.iso_standards "
                        f"SET iso360_recurring_activities = $1::JSONB WHERE id = $2",
                        _json.dumps(iso_recurring), iso_row['id']
                    )

                await conn.execute(
                    f"UPDATE {settings.DATABASE_APP_SCHEMA}.ai_tasks SET iso_standard_id = $1 WHERE id = $2",
                    iso_row['id'], task_id
                )

                for tmpl in templates:
                    # Support both formal (sections) and legacy (fixed_sections) formats
                    total_fixed = len(tmpl.get('fixed_sections', tmpl.get('sections', [])))
                    structure_json = _json.dumps({**tmpl, "template_format": template_format})
                    # Count unique {{key}} tokens across entire template JSON
                    total_fillable = len(set(re.findall(r'\{\{([^}]+)\}\}', structure_json)))
                    semantic_tags = []
                    covered_clauses = tmpl.get('covered_clauses', [])
                    covered_controls = tmpl.get('covered_controls', [])
                    tmpl_recurring_acts = tmpl.get('recurring_activities', [])
                    await conn.execute(
                        f"""
                        INSERT INTO {settings.DATABASE_APP_SCHEMA}.templates
                            (name, description, iso_standard, template_structure, ai_task_id,
                             status, total_fixed_sections, total_fillable_sections, semantic_tags,
                             covered_clauses, covered_controls, recurring_activities, created_at)
                        VALUES ($1, $2, $3, $4::JSONB, $5, 'draft', $6, $7, $8, $9, $10, $11::JSONB, NOW())
                        """,
                        tmpl.get('name', 'Untitled'),
                        f"Covers clauses: {', '.join(tmpl.get('covered_clauses', []))}" if tmpl.get('covered_clauses') else f"Auto-generated from {iso_code}",
                        iso_code, structure_json, task_id,
                        total_fixed, total_fillable, semantic_tags,
                        covered_clauses, covered_controls,
                        _json.dumps(tmpl_recurring_acts),
                    )

            await on_progress(95, f"Linking {len(templates)} templates to ISO standard...")

            async with db_client._pool.acquire() as conn:
                tmpl_rows = await conn.fetch(
                    f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE ai_task_id = $1", task_id
                )
                for row in tmpl_rows:
                    await conn.execute(
                        f"""
                        INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_iso_mapping
                            (template_id, iso_standard_id, created_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        row['id'], iso_row['id']
                    )

            cost_usd = result.get('cost_usd') or 0
            tokens_input = result.get('tokens_input') or 0
            tokens_output = result.get('tokens_output') or 0

            await db_client.save_task_result(
                task_id=task_id,
                result={"iso_standard_id": iso_standard_id, "templates_created": len(templates), "summary": summary},
                cost_usd=cost_usd,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                duration_seconds=result.get('duration_seconds'),
            )

            # Write to ai_usage_log
            try:
                async with db_client._pool.acquire() as conn:
                    await conn.execute(
                        f"""
                        INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_usage_log
                            (task_id, operation_type, provider, model, tokens_input, tokens_output,
                             cost_usd, duration_ms, status, related_entity_type, related_entity_id,
                             created_by, started_at, completed_at)
                        VALUES ($1, 'iso_build', $2, $3, $4, $5, $6, $7, 'success', 'iso_standard', $8,
                                $9, NOW() - ($10 || ' milliseconds')::interval, NOW())
                        """,
                        task_id, effective_provider, effective_model,
                        tokens_input, tokens_output, cost_usd, duration_ms,
                        iso_row['id'],
                        int(created_by) if created_by else None,
                        str(duration_ms),
                    )
            except Exception as log_err:
                logger.warning(f"Failed to write ai_usage_log: {log_err}")

            await progress_publisher.publish_completion(
                task_id=task_id,
                result_summary={"iso_standard_id": iso_standard_id, "templates_created": len(templates)}
            )
            logger.info(f"ISO build task {task_id} complete: {iso_code}, {len(templates)} templates, cost=${cost_usd:.4f}")

        except Exception as e:
            logger.error(f"ISO build task {task_id} failed: {e}")
            import traceback; traceback.print_exc()
            # Log failure to ai_usage_log
            try:
                duration_ms = int((_time.time() - task_start) * 1000)
                async with db_client._pool.acquire() as conn:
                    await conn.execute(
                        f"""
                        INSERT INTO {settings.DATABASE_APP_SCHEMA}.ai_usage_log
                            (task_id, operation_type, provider, model, duration_ms, status, error_message,
                             created_by, started_at, completed_at)
                        VALUES ($1, 'iso_build', $2, $3, $4, 'failed', $5, $6,
                                NOW() - ($4 || ' milliseconds')::interval, NOW())
                        """,
                        task_id, effective_provider, effective_model, duration_ms, str(e),
                        int(created_by) if created_by else None,
                    )
            except Exception: pass
            await self._handle_task_error(task_id=task_id, error=str(e), error_type="iso_build_error", recoverable=False)

    async def _handle_review_task(self, data: Dict[str, Any]):
        """
        Handle template review task.

        Args:
            data: Task data from stream
        """
        task_id = data.get('task_id')
        logger.info(f"Processing review task: {task_id}")

        # TODO: Implement in Milestone 2.3 (Reviewer Agent)
        logger.warning(f"Task {task_id}: Review not yet implemented")

    # ── ISO360 TEMPLATE GENERATION ──────────────────────────────

    async def _handle_iso360_template_job(self, data: Dict[str, Any]):
        """
        Handle ISO360 template generation job from ai:iso360_template stream.

        Reads recurring activities for the ISO standard, calls LLM to generate
        task/evidence templates for each activity, saves results to DB,
        and writes progress to Redis key iso360_job:{job_id}.
        """
        import traceback as _tb
        from db_client import (
            get_ai_config_for_service, get_iso_standard_with_placeholders,
            get_iso_recurring_activities, get_iso360_template_by_key,
            create_iso360_template, link_iso360_template_to_standard,
            get_ai_prompt,
        )

        job_id          = data.get("job_id", "")
        iso_standard_id = data.get("iso_standard_id", "")

        if not job_id or not iso_standard_id:
            logger.error("ISO360 template job: missing job_id or iso_standard_id")
            return

        async def _set_status(status_data: dict):
            await redis_client._client.set(
                f"iso360_job:{job_id}",
                json.dumps(status_data),
                ex=3600,
            )

        try:
            std = await get_iso_standard_with_placeholders(iso_standard_id)
            if not std:
                await _set_status({"status": "failed", "error": "ISO standard not found"})
                return

            # Primary source: recurring_activities from templates + iso-level
            recurring = await get_iso_recurring_activities(iso_standard_id)

            # Fallback: if standard hasn't been rebuilt after migration 024,
            # fall back to placeholder_dictionary filtering (old behaviour)
            if not recurring:
                placeholder_dict = std.get("placeholder_dictionary") or []
                recurring = [
                    {
                        "key": e.get("key"),
                        "title": e.get("label") or e.get("key", "").replace("_", " ").title(),
                        "iso_clause": e.get("category", ""),
                        "type": e.get("type", "review"),
                        "update_frequency": e.get("update_frequency", "yearly"),
                        "description": e.get("question", ""),
                        "related_placeholder_keys": [],
                        "template_name": None,
                        "source": "placeholder_fallback",
                    }
                    for e in placeholder_dict
                    if isinstance(e, dict)
                    and e.get("lifecycle") == "recurring"
                    and e.get("type") in ("review", "operational_activity", "record")
                    and e.get("update_frequency") in ("monthly", "quarterly", "yearly", "event_based")
                ]

            total = len(recurring)
            await _set_status({
                "status": "running",
                "progress": 0,
                "total": total,
                "done": 0,
                "current_key": None,
                "iso_code": std["code"],
            })

            if total == 0:
                await _set_status({
                    "status": "completed",
                    "progress": 100,
                    "total": 0,
                    "done": 0,
                    "iso_code": std["code"],
                    "message": (
                        "No recurring activities found. "
                        "Rebuild the ISO standard so the LLM populates recurring_activities per template."
                    ),
                })
                return

            ai_cfg = await get_ai_config_for_service("iso360_template_builder")

            # Fetch prompts once
            system_row = await get_ai_prompt("iso360_template_system")
            user_row   = await get_ai_prompt("iso360_template_user")

            if not system_row or not user_row:
                logger.warning("ISO360 template job: prompts not found in ai_prompts table — using fallback for all")
                system_prompt = None
                user_template = None
            else:
                system_prompt = system_row["prompt_text"]
                user_template = user_row["prompt_text"]

            # Build an agent instance for this job
            from agents.iso360_template_agent import ISO360TemplateAgent, _fallback as _tmpl_fallback
            agent = ISO360TemplateAgent(
                api_key=ai_cfg.get("_api_key", ""),
                model=ai_cfg.get("model") or "gemini-2.5-flash",
                provider=ai_cfg.get("provider", "gemini"),
            )

            _VALID_FREQ = {"monthly", "quarterly", "yearly", "event_based"}

            done = skipped = created = 0

            for entry in recurring:
                key = entry.get("key") or ""
                await _set_status({
                    "status": "running",
                    "progress": int(done / total * 100),
                    "total": total,
                    "done": done,
                    "current_key": key,
                    "iso_code": std["code"],
                })

                # Reuse existing template if one already exists for this key
                existing = await get_iso360_template_by_key(key)
                if existing:
                    await link_iso360_template_to_standard(
                        str(existing["id"]), iso_standard_id,
                        [entry.get("iso_clause") or entry.get("category", "")],
                    )
                    skipped += 1
                    done += 1
                    logger.debug(f"ISO360 template reused: key={key!r}")
                    continue

                _raw_freq = entry.get("update_frequency") or "yearly"
                _update_freq = _raw_freq if _raw_freq in _VALID_FREQ else "event_based"

                try:
                    if system_prompt and user_template:
                        tmpl = await agent.generate_iso360_template(
                            placeholder_key=key,
                            type_=entry.get("type", "review"),
                            update_frequency=_update_freq,
                            iso_clause=entry.get("iso_clause") or entry.get("category", ""),
                            category=entry.get("template_name") or entry.get("category", ""),
                            iso_standard_name=std["name"],
                            description=entry.get("description", ""),
                            system_prompt=system_prompt,
                            user_template=user_template,
                        )
                    else:
                        tmpl = _tmpl_fallback(key)

                    template_id = await create_iso360_template(
                        placeholder_key=key,
                        type_=entry.get("type", "review"),
                        update_frequency=_update_freq,
                        title=tmpl.get("title") or entry.get("title") or key.replace("_", " ").title(),
                        responsible_role=tmpl["responsible_role"],
                        steps=tmpl["steps"],
                        evidence_fields=tmpl["evidence_fields"],
                    )
                    await link_iso360_template_to_standard(
                        template_id, iso_standard_id,
                        [entry.get("iso_clause") or entry.get("category", "")],
                    )
                    created += 1
                    logger.info(f"ISO360 template created: key={key!r}, id={template_id[:8]}")
                except Exception as e:
                    logger.error(f"ISO360 template failed for key={key!r}: {e}")

                done += 1

            await _set_status({
                "status": "completed",
                "progress": 100,
                "total": total,
                "done": done,
                "created": created,
                "skipped": skipped,
                "iso_code": std["code"],
            })
            logger.info(
                f"ISO360 template job {job_id} completed: "
                f"created={created}, skipped={skipped}, total={total}"
            )

        except Exception as e:
            logger.error(f"ISO360 template job {job_id} failed: {e}\n{_tb.format_exc()}")
            await _set_status({"status": "failed", "error": str(e)})

    # ── ISO360 CUSTOMER ADJUSTMENT ──────────────────────────────

    async def _handle_iso360_adjustment_job(self, data: Dict[str, Any]):
        """
        Handle ISO360 customer adjustment job from ai:iso360_adjustment stream.

        Step 1 (1 LLM call): Synthesise KYC answers → structured summary + Mermaid graph.
                              Stored in iso360_kyc_batches. Skipped if already generated.
        Step 2 (N parallel LLM calls): Personalise each ISO360 template using the compact
                              summary instead of raw answers. All templates run concurrently.

        Progress is written to Redis key iso360_adjustment_job:{job_id}.
        """
        import asyncio as _asyncio
        import traceback as _tb
        from datetime import date
        from db_client import (
            get_ai_config_for_service, get_ai_prompt,
            get_iso360_templates_for_standard,
            get_customer_info, save_iso360_customer_document, mark_adjustment_pass_done,
            get_kyc_batch_summary, save_kyc_batch_summary, get_kyc_answers_for_batch,
        )

        job_id              = data.get("job_id", "unknown")
        plan_id             = data.get("plan_id", "")
        customer_id_raw     = data.get("customer_id", "")
        iso_standard_id     = data.get("iso_standard_id", "")
        iso_standard_code   = data.get("iso_standard", "")
        reminder_month_raw  = data.get("reminder_month", "")
        reminder_day_raw    = data.get("reminder_day", "")
        kyc_batch_id        = data.get("kyc_batch_id", "")

        customer_id    = int(customer_id_raw)    if customer_id_raw    and str(customer_id_raw).isdigit()    else None
        reminder_month = int(reminder_month_raw) if reminder_month_raw and str(reminder_month_raw).isdigit() else None
        reminder_day   = int(reminder_day_raw)   if reminder_day_raw   and str(reminder_day_raw).isdigit()   else None

        async def _set_status(status_data: dict):
            await redis_client._client.set(
                f"iso360_adjustment_job:{job_id}",
                json.dumps(status_data),
                ex=3600,
            )

        def _compute_next_due(update_frequency: str, r_month: int | None, r_day: int | None) -> date | None:
            today = date.today()
            if update_frequency == "event_based":
                return None
            if update_frequency == "yearly":
                if r_month and r_day:
                    try:
                        candidate = date(today.year, r_month, r_day)
                        if candidate <= today:
                            candidate = date(today.year + 1, r_month, r_day)
                        return candidate
                    except ValueError:
                        pass
                return date(today.year + 1, today.month, today.day)
            if update_frequency == "quarterly":
                quarter_starts = [1, 4, 7, 10]
                for qs in quarter_starts:
                    candidate = date(today.year, qs, 1)
                    if candidate > today:
                        return candidate
                return date(today.year + 1, 1, 1)
            if update_frequency == "monthly":
                if today.month == 12:
                    return date(today.year + 1, 1, 1)
                return date(today.year, today.month + 1, 1)
            return None

        try:
            await _set_status({
                "status": "starting",
                "plan_id": plan_id,
                "iso_standard": iso_standard_code,
            })

            if not iso_standard_id:
                await _set_status({"status": "failed", "error": "missing iso_standard_id"})
                return
            if not customer_id:
                await _set_status({"status": "failed", "error": "missing or invalid customer_id"})
                return
            if not plan_id:
                await _set_status({"status": "failed", "error": "missing plan_id"})
                return

            # Load all templates for this ISO standard
            templates = await get_iso360_templates_for_standard(iso_standard_id)
            total = len(templates)

            if total == 0:
                logger.info(
                    f"ISO360 adjustment job {job_id}: no templates found for "
                    f"iso_standard_id={iso_standard_id} — marking done"
                )
                await mark_adjustment_pass_done(plan_id)
                await _set_status({
                    "status": "completed",
                    "progress": 100,
                    "total": 0,
                    "done": 0,
                    "message": "No ISO360 templates found for this standard.",
                })
                return

            customer_info     = await get_customer_info(customer_id)
            customer_industry = customer_info.get("industry", "")
            customer_size     = customer_info.get("size", "")
            customer_name     = customer_info.get("name", "") or customer_info.get("company_name", "")

            ai_cfg = await get_ai_config_for_service("iso360_adjustment")

            # ── Step 1: KYC Summary (1 LLM call, cached per batch) ──────────────
            await _set_status({
                "status": "summarising",
                "plan_id": plan_id,
                "iso_standard": iso_standard_code,
                "total": total,
            })

            customer_context = ""  # compact string passed to each template adjustment

            if kyc_batch_id:
                existing_summary, existing_graph = await get_kyc_batch_summary(kyc_batch_id)
            else:
                existing_summary, existing_graph = None, None

            if existing_summary:
                # Reuse cached summary — no LLM call needed
                from agents.iso360_summary_agent import format_summary_for_prompt
                customer_context = format_summary_for_prompt(existing_summary)
                logger.info(
                    f"ISO360 adjustment job {job_id}: reusing cached KYC summary "
                    f"for batch={kyc_batch_id}"
                )
            else:
                # Generate summary from KYC answers
                summary_system_row = await get_ai_prompt("iso360_kyc_summary_system")
                summary_user_row   = await get_ai_prompt("iso360_kyc_summary_user")

                if summary_system_row and summary_user_row and kyc_batch_id:
                    kyc_answers_raw = await get_kyc_answers_for_batch(kyc_batch_id)
                    from agents.iso360_summary_agent import ISO360SummaryAgent, format_summary_for_prompt
                    summary_agent = ISO360SummaryAgent(
                        api_key=ai_cfg.get("_api_key", ""),
                        model=ai_cfg.get("model") or "gemini-2.5-flash",
                        provider=ai_cfg.get("provider", "gemini"),
                    )
                    summary_dict, graph_str = await summary_agent.generate_summary(
                        kyc_answers=kyc_answers_raw,
                        customer_name=customer_name,
                        industry=customer_industry,
                        company_size=customer_size,
                        iso_code=iso_standard_code,
                        system_prompt=summary_system_row["prompt_text"],
                        user_template=summary_user_row["prompt_text"],
                        trace_id=job_id,
                    )
                    await save_kyc_batch_summary(kyc_batch_id, summary_dict, graph_str)
                    customer_context = format_summary_for_prompt(summary_dict)
                    logger.info(
                        f"ISO360 adjustment job {job_id}: KYC summary generated and saved "
                        f"for batch={kyc_batch_id}"
                    )
                else:
                    # No KYC batch or prompts missing — fall back to raw answers
                    from db_client import get_customer_answers_context
                    customer_context = await get_customer_answers_context(customer_id, plan_id)
                    logger.warning(
                        f"ISO360 adjustment job {job_id}: no KYC batch / summary prompts, "
                        f"falling back to raw answers"
                    )

            # ── Step 2: Template adjustment prompts ──────────────────────────────
            system_row = await get_ai_prompt("iso360_adjustment_system")
            user_row   = await get_ai_prompt("iso360_adjustment_user")

            if not system_row or not user_row:
                logger.warning(
                    f"ISO360 adjustment job: prompts not found — will copy templates verbatim"
                )
                system_prompt = None
                user_template = None
            else:
                system_prompt = system_row["prompt_text"]
                user_template = user_row["prompt_text"]

            from agents.iso360_adjustment_agent import ISO360AdjustmentAgent
            agent = ISO360AdjustmentAgent(
                api_key=ai_cfg.get("_api_key", ""),
                model=ai_cfg.get("model") or "gemini-2.5-flash",
                provider=ai_cfg.get("provider", "gemini"),
            )

            await _set_status({
                "status": "running",
                "progress": 0,
                "total": total,
                "done": 0,
                "iso_standard": iso_standard_code,
            })

            # ── Parallel execution — all templates at once ───────────────────────
            async def _adjust_and_save(tmpl: dict) -> bool:
                """Adjust one template and save. Returns True on success."""
                key = tmpl.get("placeholder_key") or str(tmpl["id"])
                try:
                    if system_prompt and user_template:
                        adjusted = await agent.adjust_iso360_template(
                            placeholder_key=key,
                            template_steps=tmpl.get("steps") or [],
                            evidence_fields=tmpl.get("evidence_fields") or [],
                            customer_answers=customer_context,
                            customer_industry=customer_industry,
                            customer_size=customer_size,
                            system_prompt=system_prompt,
                            user_template=user_template,
                        )
                    else:
                        adjusted = {
                            "steps": tmpl.get("steps") or [],
                            "evidence_fields": tmpl.get("evidence_fields") or [],
                        }

                    personalized_content = {
                        "title":            tmpl.get("title", key.replace("_", " ").title()),
                        "responsible_role": tmpl.get("responsible_role", "Compliance Manager"),
                        "steps":            adjusted.get("steps") or tmpl.get("steps") or [],
                        "evidence_fields":  adjusted.get("evidence_fields") or tmpl.get("evidence_fields") or [],
                        "placeholder_key":  key,
                        "type":             tmpl.get("type", "review"),
                        "update_frequency": tmpl.get("update_frequency", "yearly"),
                    }

                    next_due = _compute_next_due(
                        tmpl.get("update_frequency", "yearly"),
                        reminder_month,
                        reminder_day,
                    )

                    doc_id = await save_iso360_customer_document(
                        customer_id=customer_id,
                        plan_id=plan_id,
                        iso_standard_id=iso_standard_code,
                        template=tmpl,
                        personalized_content=personalized_content,
                        next_due_date=next_due,
                    )
                    logger.info(
                        f"ISO360 adjustment job {job_id}: "
                        f"key={key!r} → doc_id={doc_id[:8]}, due={next_due}"
                    )
                    return True
                except Exception as e:
                    logger.error(
                        f"ISO360 adjustment job {job_id}: failed for key={key!r}: {e}"
                    )
                    return False

            results = await _asyncio.gather(
                *[_adjust_and_save(tmpl) for tmpl in templates],
                return_exceptions=True,
            )
            saved = sum(1 for r in results if r is True)

            # Mark adjustment pass done so scheduler doesn't re-queue this plan
            await mark_adjustment_pass_done(plan_id)

            await _set_status({
                "status": "completed",
                "progress": 100,
                "total": total,
                "done": total,
                "saved": saved,
                "iso_standard": iso_standard_code,
            })
            logger.info(
                f"ISO360 adjustment job {job_id} completed: "
                f"plan={plan_id[:8] if len(plan_id) >= 8 else plan_id}, customer={customer_id}, "
                f"total={total}, saved={saved}"
            )

        except Exception as e:
            logger.error(f"ISO360 adjustment job {job_id} failed: {e}\n{_tb.format_exc()}")
            await _set_status({"status": "failed", "error": str(e)})

    # ── ISO360 KYC QUESTIONNAIRE ─────────────────────────────────

    async def _handle_iso360_kyc_job(self, data: Dict[str, Any]):
        """
        Handle ISO360 KYC question generation from ai:iso360_kyc stream.

        Generates ~10 onboarding compliance questions for a customer+plan,
        saves them as customer_tasks (task_type='kyc_question'),
        and updates the iso360_kyc_batches row.
        """
        import traceback as _tb
        import uuid as _uuid
        from db_client import get_ai_config_for_service, get_ai_prompt

        batch_id      = data.get("batch_id", "")
        customer_id   = int(data["customer_id"]) if str(data.get("customer_id", "")).isdigit() else None
        plan_id       = data.get("plan_id", "")
        iso_code      = data.get("iso_code", "")
        iso_name      = data.get("iso_name", "")
        customer_name = data.get("customer_name", "")
        industry      = data.get("industry", "")
        company_size  = data.get("company_size", "")
        language      = data.get("language", "en")

        async def _fail(msg: str):
            async with db_client._pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE {settings.DATABASE_APP_SCHEMA}.iso360_kyc_batches"
                    f" SET status='failed', error_message=$1 WHERE id=$2::uuid",
                    msg, batch_id,
                )
            logger.error(f"KYC job {batch_id} failed: {msg}")

        try:
            if not customer_id or not plan_id or not batch_id:
                await _fail("Missing required fields: customer_id, plan_id, or batch_id")
                return

            # Fetch prompts
            system_row = await get_ai_prompt("iso360_kyc_system")
            user_row   = await get_ai_prompt("iso360_kyc_user")
            if not system_row or not user_row:
                await _fail("KYC prompts not found in ai_prompts table")
                return

            system_prompt = system_row["prompt_text"]
            user_template = user_row["prompt_text"]

            # Fill template variables
            lang_label = "Hebrew" if language == "he" else "English"
            user_prompt = (
                user_template
                .replace("{{iso_code}}",      iso_code)
                .replace("{{customer_name}}", customer_name)
                .replace("{{industry}}",      industry or "Not specified")
                .replace("{{company_size}}",  company_size or "Not specified")
                .replace("{{language}}",      lang_label)
            )
            system_prompt = system_prompt.replace("{{language}}", lang_label)

            # Call LLM via BaseAgent pattern (same as adjustment agent)
            ai_cfg = await get_ai_config_for_service("iso360_adjustment")
            from agents.base_agent import BaseAgent
            from typing import Optional as _Opt

            class _KYCAgent(BaseAgent):
                @property
                def agent_name(self) -> str:
                    return "KYCAgent"

            agent = _KYCAgent(
                api_key=ai_cfg.get("_api_key", ""),
                model=ai_cfg.get("model") or "gemini-2.5-flash",
                provider=ai_cfg.get("provider", "gemini"),
            )
            result = await agent._call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            raw_response = result.get("content", "")

            # Parse JSON response
            import re as _re
            raw_text = raw_response.strip()
            # Strip markdown code fences if present
            raw_text = _re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = _re.sub(r"\s*```$", "", raw_text.strip())
            questions = json.loads(raw_text)

            if not isinstance(questions, list) or len(questions) == 0:
                await _fail("LLM returned empty or non-list questions")
                return

            # Save tasks and update batch
            async with db_client._pool.acquire() as conn:
                task_ids = []
                for q in questions:
                    key      = q.get("key") or f"kyc_{_uuid.uuid4().hex[:8]}"
                    question = q.get("question", "")
                    category = q.get("category", "general")
                    hint     = q.get("hint", "")
                    task_id = await conn.fetchval(
                        f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks
                                (customer_id, plan_id, task_type, task_scope,
                                 title, description, status, priority,
                                 placeholder_key, auto_generated, source,
                                 kyc_batch_id, created_at, updated_at)
                            VALUES ($1, $2::uuid, 'kyc_question', 'plan',
                                    $3, $4, 'pending', 'medium',
                                    $5, TRUE, 'iso360_kyc',
                                    $6::uuid, NOW(), NOW())
                            RETURNING id""",
                        customer_id, plan_id,
                        question,
                        f"[{category}] {hint}" if hint else category,
                        key,
                        batch_id,
                    )
                    task_ids.append(task_id)

                # Update batch: status → pending, total_questions set
                await conn.execute(
                    f"""UPDATE {settings.DATABASE_APP_SCHEMA}.iso360_kyc_batches
                        SET status = 'pending', total_questions = $1
                        WHERE id = $2::uuid""",
                    len(task_ids), batch_id,
                )

            # Push initial collection email send for KYC questions
            await redis_client._client.xadd("automation:send", {
                "customer_id": str(customer_id),
                "plan_id":     plan_id,
                "iso_code":    iso_code,
                "iso_name":    iso_name,
                "is_kyc":      "true",
                "language":    language,
            })

            logger.info(
                f"KYC job {batch_id}: generated {len(task_ids)} questions "
                f"for customer={customer_id}, plan={plan_id} — send queued"
            )

        except Exception as e:
            logger.error(f"KYC job {batch_id} error: {e}\n{_tb.format_exc()}")
            await _fail(str(e))


# Global consumer instance
stream_consumer = StreamConsumer()
