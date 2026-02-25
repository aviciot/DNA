"""
Redis Stream Consumer
=====================

Consumes tasks from Redis Streams and processes them.
"""

import asyncio
import json
import logging
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
                prow = await conn.fetchrow(
                    f"SELECT value FROM {settings.DATABASE_APP_SCHEMA}.ai_settings WHERE key = 'active_provider'"
                )
                mrow = await conn.fetchrow(
                    f"SELECT value FROM {settings.DATABASE_APP_SCHEMA}.ai_settings WHERE key = 'active_model'"
                )
            if prow:
                provider = prow["value"]
            if mrow:
                active_model = mrow["value"]
            logger.info(f"AI config from DB: provider={provider}, model={active_model}")
        except Exception as e:
            logger.warning(f"Could not read ai_settings from DB, using env vars: {e}")

        # Initialize template agent — provider/model resolved from DB above
        api_key, model = None, None
        if provider == "gemini":
            api_key = settings.GOOGLE_API_KEY
            model = active_model or settings.GEMINI_MODEL
        elif provider == "anthropic":
            api_key = settings.ANTHROPIC_API_KEY
            model = active_model or settings.ANTHROPIC_MODEL
        elif provider == "groq":
            api_key = settings.GROQ_API_KEY
            model = active_model or settings.GROQ_MODEL

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

                await conn.execute(
                    f"UPDATE {settings.DATABASE_APP_SCHEMA}.ai_tasks SET iso_standard_id = $1 WHERE id = $2",
                    iso_row['id'], task_id
                )

                for tmpl in templates:
                    structure_json = _json.dumps({**tmpl, "template_format": template_format})
                    total_fixed = len(tmpl.get('fixed_sections', []))
                    total_fillable = len(tmpl.get('fillable_sections', []))
                    semantic_tags = list({tag for s in tmpl.get('fillable_sections', []) for tag in s.get('semantic_tags', [])})
                    covered_clauses = tmpl.get('covered_clauses', [])
                    covered_controls = tmpl.get('covered_controls', [])
                    await conn.execute(
                        f"""
                        INSERT INTO {settings.DATABASE_APP_SCHEMA}.templates
                            (name, description, iso_standard, template_structure, ai_task_id,
                             status, total_fixed_sections, total_fillable_sections, semantic_tags,
                             covered_clauses, covered_controls, created_at)
                        VALUES ($1, $2, $3, $4::JSONB, $5, 'draft', $6, $7, $8, $9, $10, NOW())
                        """,
                        tmpl.get('name', 'Untitled'),
                        f"Covers clauses: {', '.join(tmpl.get('covered_clauses', []))}" if tmpl.get('covered_clauses') else f"Auto-generated from {iso_code}",
                        iso_code, structure_json, task_id,
                        total_fixed, total_fillable, semantic_tags,
                        covered_clauses, covered_controls,
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


# Global consumer instance
stream_consumer = StreamConsumer()
