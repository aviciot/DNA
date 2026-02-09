"""
Telemetry Logging Utility
==========================

Structured logging designed as telemetry events.
Currently outputs to stdout, but structured for future Redis publishing.

Usage:
    from telemetry import telemetry

    telemetry.event(
        event_type="agent.started",
        task_id=task_id,
        trace_id=trace_id,
        data={"agent": "TemplateAgent", "file": "iso9001.docx"}
    )
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelemetryLogger:
    """
    Telemetry-style structured logging.

    Logs are structured as events with:
    - trace_id: Links all events in a user operation chain
    - event_type: Category of event (agent.started, llm.request, etc.)
    - context: task_id, user_id, session_id
    - data: Event-specific payload

    Future: Can switch from stdout to Redis streams with minimal code change.
    """

    def __init__(self, service_name: str = "ai-service"):
        self.service_name = service_name
        self.logger = logging.getLogger(f"telemetry.{service_name}")

    def event(
        self,
        event_type: str,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        user_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a telemetry event.

        Args:
            event_type: Event category (e.g., "agent.started", "llm.request")
            trace_id: Trace ID linking all events in operation chain
            task_id: Task UUID
            user_id: User ID who initiated operation
            data: Event-specific data
            metadata: Additional metadata (agent name, model, etc.)
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "service": self.service_name,

            # Context
            "trace_id": trace_id,
            "task_id": task_id,
            "user_id": user_id,

            # Payload
            "data": data or {},
            "metadata": metadata or {}
        }

        # Log as structured JSON
        self.logger.info(json.dumps(event))

    def operation_started(
        self,
        operation_name: str,
        trace_id: str,
        task_id: str,
        user_id: Optional[int] = None,
        **context
    ):
        """Log operation start (user-friendly business operation)."""
        self.event(
            event_type="operation.started",
            trace_id=trace_id,
            task_id=task_id,
            user_id=user_id,
            data={
                "operation": operation_name,
                **context
            }
        )

    def operation_progress(
        self,
        operation_name: str,
        trace_id: str,
        task_id: str,
        progress: int,
        current_step: str,
        eta_seconds: Optional[int] = None
    ):
        """Log operation progress update."""
        self.event(
            event_type="operation.progress",
            trace_id=trace_id,
            task_id=task_id,
            data={
                "operation": operation_name,
                "progress": progress,
                "current_step": current_step,
                "eta_seconds": eta_seconds
            }
        )

    def operation_completed(
        self,
        operation_name: str,
        trace_id: str,
        task_id: str,
        duration_seconds: int,
        result_summary: Dict[str, Any]
    ):
        """Log operation completion."""
        self.event(
            event_type="operation.completed",
            trace_id=trace_id,
            task_id=task_id,
            data={
                "operation": operation_name,
                "duration_seconds": duration_seconds,
                "result_summary": result_summary
            }
        )

    def operation_failed(
        self,
        operation_name: str,
        trace_id: str,
        task_id: str,
        error: str,
        error_type: str
    ):
        """Log operation failure."""
        self.event(
            event_type="operation.failed",
            trace_id=trace_id,
            task_id=task_id,
            data={
                "operation": operation_name,
                "error": error,
                "error_type": error_type
            }
        )

    def agent_started(
        self,
        agent_name: str,
        trace_id: str,
        task_id: str,
        **context
    ):
        """Log agent start."""
        self.event(
            event_type="agent.started",
            trace_id=trace_id,
            task_id=task_id,
            metadata={"agent": agent_name},
            data=context
        )

    def agent_operation(
        self,
        agent_name: str,
        operation: str,
        trace_id: str,
        task_id: str,
        **context
    ):
        """Log agent operation step."""
        self.event(
            event_type="agent.operation",
            trace_id=trace_id,
            task_id=task_id,
            metadata={"agent": agent_name},
            data={"operation": operation, **context}
        )

    def agent_completed(
        self,
        agent_name: str,
        trace_id: str,
        task_id: str,
        duration_seconds: int,
        result_summary: Dict[str, Any]
    ):
        """Log agent completion."""
        self.event(
            event_type="agent.completed",
            trace_id=trace_id,
            task_id=task_id,
            metadata={"agent": agent_name},
            data={
                "duration_seconds": duration_seconds,
                "result_summary": result_summary
            }
        )

    def agent_failed(
        self,
        agent_name: str,
        trace_id: str,
        task_id: str,
        error: str,
        error_type: str
    ):
        """Log agent failure."""
        self.event(
            event_type="agent.failed",
            trace_id=trace_id,
            task_id=task_id,
            metadata={"agent": agent_name},
            data={
                "error": error,
                "error_type": error_type
            }
        )

    def llm_request(
        self,
        provider: str,
        model: str,
        trace_id: str,
        task_id: str,
        prompt_type: str,
        input_tokens: Optional[int] = None
    ):
        """Log LLM API request."""
        self.event(
            event_type="llm.request",
            trace_id=trace_id,
            task_id=task_id,
            metadata={
                "provider": provider,
                "model": model
            },
            data={
                "prompt_type": prompt_type,
                "input_tokens": input_tokens
            }
        )

    def llm_response(
        self,
        provider: str,
        model: str,
        trace_id: str,
        task_id: str,
        duration_ms: int,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ):
        """Log LLM API response."""
        self.event(
            event_type="llm.response",
            trace_id=trace_id,
            task_id=task_id,
            metadata={
                "provider": provider,
                "model": model
            },
            data={
                "duration_ms": duration_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd
            }
        )

    def error(
        self,
        error_type: str,
        error_message: str,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        **context
    ):
        """Log error event."""
        self.event(
            event_type="error",
            trace_id=trace_id,
            task_id=task_id,
            data={
                "error_type": error_type,
                "error_message": error_message,
                **context
            }
        )


# Global telemetry instance
telemetry = TelemetryLogger(service_name="ai-service")


# Convenience function for creating trace IDs
def generate_trace_id() -> str:
    """Generate a new trace ID for tracking operation chains."""
    return str(uuid.uuid4())
