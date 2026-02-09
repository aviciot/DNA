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
from progress_publisher import progress_publisher
from telemetry import telemetry, generate_trace_id

logger = logging.getLogger(__name__)


class StreamConsumer:
    """Redis Stream consumer for AI tasks."""

    def __init__(self):
        self.consumer_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.tasks: Dict[str, asyncio.Task] = {}
        self.template_agent: Optional[TemplateAgent] = None

    async def start(self):
        """Start consuming from streams."""
        logger.info(f"Starting stream consumer: {self.consumer_id}")

        # Connect to Redis and Database
        await redis_client.connect()
        await db_client.connect()

        # Test connections
        if await redis_client.ping():
            logger.info("✓ Redis connection verified")
        else:
            raise RuntimeError("Redis connection failed")

        # Create consumer groups
        await self._create_consumer_groups()

        # Initialize template agent with configured provider
        if settings.LLM_PROVIDER == "gemini":
            if settings.GOOGLE_API_KEY:
                self.template_agent = TemplateAgent(
                    api_key=settings.GOOGLE_API_KEY,
                    model=settings.GEMINI_MODEL,
                    max_tokens=16384,
                    provider="gemini"
                )
                logger.info(f"✓ Template agent initialized (provider=gemini, model={settings.GEMINI_MODEL}, max_tokens=16384)")
            else:
                logger.warning("GOOGLE_API_KEY not set - cannot use Gemini provider")
        else:  # anthropic
            if settings.ANTHROPIC_API_KEY:
                self.template_agent = TemplateAgent(
                    api_key=settings.ANTHROPIC_API_KEY,
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=16384,
                    provider="anthropic"
                )
                logger.info(f"✓ Template agent initialized (provider=anthropic, model={settings.ANTHROPIC_MODEL}, max_tokens=16384)")
            else:
                logger.warning("ANTHROPIC_API_KEY not set - cannot use Anthropic provider")

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
            ("template:review", "reviewer-workers")
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
