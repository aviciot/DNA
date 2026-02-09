"""
Progress Publisher
==================

Publishes detailed progress updates with ETA calculations and user-friendly messages.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time

from redis_client import redis_client

logger = logging.getLogger(__name__)


class ProgressPublisher:
    """
    Publishes progress updates with ETA calculations.

    Features:
    - Calculates estimated time remaining
    - Tracks processing speed
    - User-friendly progress messages
    - Error state handling
    """

    def __init__(self):
        self.task_start_times: Dict[str, float] = {}
        self.last_progress: Dict[str, int] = {}

    async def publish_progress(
        self,
        task_id: str,
        progress: int,
        current_step: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Publish progress update with ETA.

        Args:
            task_id: Task UUID
            progress: Progress percentage (0-100)
            current_step: User-friendly description
            details: Optional additional details (sections found, fields extracted, etc.)
        """
        # Track start time
        if task_id not in self.task_start_times:
            self.task_start_times[task_id] = time.time()

        # Calculate elapsed time
        elapsed_seconds = int(time.time() - self.task_start_times[task_id])

        # Calculate ETA
        eta_seconds = None
        if progress > 0 and progress < 100:
            # Time per percent
            time_per_percent = elapsed_seconds / progress
            remaining_percent = 100 - progress
            eta_seconds = int(time_per_percent * remaining_percent)

        # Build message
        message = {
            "type": "progress_update",
            "task_id": task_id,
            "progress": progress,
            "current_step": current_step,
            "elapsed_seconds": elapsed_seconds,
            "eta_seconds": eta_seconds,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add optional details
        if details:
            message["details"] = details

        # Add user-friendly ETA message
        if eta_seconds:
            message["eta_message"] = self._format_eta(eta_seconds)

        # Store last progress
        self.last_progress[task_id] = progress

        # Publish to Redis Pub/Sub
        await redis_client.publish(
            channel=f"progress:task:{task_id}",
            message=message
        )

        logger.debug(f"Task {task_id}: {progress}% - {current_step} (ETA: {eta_seconds}s)")

    async def publish_completion(
        self,
        task_id: str,
        result_summary: Dict[str, Any]
    ):
        """
        Publish completion message.

        Args:
            task_id: Task UUID
            result_summary: Summary of results (sections, fields, etc.)
        """
        elapsed_seconds = int(time.time() - self.task_start_times.get(task_id, time.time()))

        message = {
            "type": "task_complete",
            "task_id": task_id,
            "progress": 100,
            "current_step": "Parsing complete!",
            "elapsed_seconds": elapsed_seconds,
            "result_summary": result_summary,
            "timestamp": datetime.utcnow().isoformat()
        }

        await redis_client.publish(
            channel=f"progress:task:{task_id}",
            message=message
        )

        # Cleanup
        self.task_start_times.pop(task_id, None)
        self.last_progress.pop(task_id, None)

        logger.info(f"Task {task_id}: Completed in {elapsed_seconds}s")

    async def publish_error(
        self,
        task_id: str,
        error_message: str,
        error_type: str = "parsing_error",
        recoverable: bool = False
    ):
        """
        Publish error message.

        Args:
            task_id: Task UUID
            error_message: User-friendly error description
            error_type: Type of error (parsing_error, file_not_found, api_error, etc.)
            recoverable: Whether the error is recoverable
        """
        message = {
            "type": "task_error",
            "task_id": task_id,
            "error": error_message,
            "error_type": error_type,
            "recoverable": recoverable,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add helpful suggestions based on error type
        if error_type == "file_not_found":
            message["suggestion"] = "Please ensure the file was uploaded correctly and try again."
        elif error_type == "api_error":
            message["suggestion"] = "The AI service is temporarily unavailable. Your task will be retried automatically."
        elif error_type == "parsing_error":
            message["suggestion"] = "There was an issue parsing your document. Please verify it's a valid Word file."

        await redis_client.publish(
            channel=f"progress:task:{task_id}",
            message=message
        )

        # Cleanup
        self.task_start_times.pop(task_id, None)
        self.last_progress.pop(task_id, None)

        logger.error(f"Task {task_id}: Error - {error_message} ({error_type})")

    def _format_eta(self, seconds: int) -> str:
        """Format ETA in user-friendly format."""
        if seconds < 60:
            return f"~{seconds} seconds remaining"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"~{minutes} minute{'s' if minutes != 1 else ''} remaining"
        else:
            hours = seconds // 3600
            return f"~{hours} hour{'s' if hours != 1 else ''} remaining"

    async def publish_milestone(
        self,
        task_id: str,
        milestone: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Publish milestone message (for major achievements).

        Args:
            task_id: Task UUID
            milestone: Milestone description
            details: Optional details about the milestone
        """
        message = {
            "type": "milestone",
            "task_id": task_id,
            "milestone": milestone,
            "timestamp": datetime.utcnow().isoformat()
        }

        if details:
            message["details"] = details

        await redis_client.publish(
            channel=f"progress:task:{task_id}",
            message=message
        )

        logger.info(f"Task {task_id}: Milestone - {milestone}")


# Global progress publisher instance
progress_publisher = ProgressPublisher()
