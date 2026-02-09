"""
Base Agent
===========

Abstract base class for all AI agents.
Provides common LLM calling patterns, telemetry integration, and error handling.
"""

import logging
import time
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from llm_client import LLMClient, get_llm_client
from gemini_client import GeminiClient, get_gemini_client
from telemetry import telemetry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.

    Features:
    - Rate-limited LLM calls via shared client
    - Integrated telemetry (operation tracking, LLM metrics)
    - JSON extraction helpers
    - Consistent error handling
    - Stateless design (pass context as parameters)

    Subclasses must implement:
    - agent_name: str property
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        provider: str = "anthropic"
    ):
        """
        Initialize base agent.

        Args:
            api_key: API key (Anthropic or Google)
            model: Model to use
            max_tokens: Max tokens per request
            provider: "anthropic" or "gemini"
        """
        self.model = model
        self.max_tokens = max_tokens
        self.provider = provider

        # Get shared LLM client based on provider
        if provider == "gemini":
            self.llm_client = get_gemini_client(
                api_key=api_key,
                model=model,
                max_tokens=max_tokens
            )
        else:
            self.llm_client = get_llm_client(
                api_key=api_key,
                model=model
            )

        logger.info(f"{self.agent_name} initialized (provider={provider}, model={model})")

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Agent name for logging/telemetry (e.g., 'TemplateAgent')."""
        pass

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        call_purpose: str = "llm_call"
    ) -> Dict[str, Any]:
        """
        Call LLM with telemetry integration.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0-1)
            trace_id: Optional trace ID for telemetry
            task_id: Optional task ID for telemetry
            call_purpose: Description of this LLM call (e.g., 'structure_analysis')

        Returns:
            {
                "content": "Response text",
                "usage": {
                    "input_tokens": 1234,
                    "output_tokens": 567,
                    "total_tokens": 1801
                },
                "cost_usd": 0.0234,
                "duration_ms": 1234,
                "model": "claude-sonnet-4-5-20250929"
            }

        Raises:
            APIError: If all retries fail
        """
        # Telemetry: LLM request started
        if trace_id:
            telemetry.llm_request(
                provider="anthropic",
                model=self.model,
                trace_id=trace_id,
                task_id=task_id,
                prompt_type=call_purpose
            )

        start_time = time.time()

        try:
            # Call LLM (rate-limited, with retry)
            result = await self.llm_client.call(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )

            # Telemetry: LLM response received
            if trace_id:
                telemetry.llm_response(
                    provider="anthropic",
                    model=self.model,
                    trace_id=trace_id,
                    task_id=task_id,
                    duration_ms=result["duration_ms"],
                    input_tokens=result["usage"]["input_tokens"],
                    output_tokens=result["usage"]["output_tokens"],
                    cost_usd=result["cost_usd"]
                )

            logger.debug(
                f"{self.agent_name}: LLM call '{call_purpose}' completed - "
                f"{result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out, "
                f"${result['cost_usd']:.4f}, {result['duration_ms']}ms"
            )

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"{self.agent_name}: LLM call '{call_purpose}' failed after {duration_ms}ms: {e}")

            # Provide user-friendly error messages
            error_msg = str(e).lower()

            if "rate limit" in error_msg or "429" in error_msg:
                raise RuntimeError(
                    f"Claude AI rate limit exceeded.\n"
                    f"The system is currently processing many requests.\n"
                    f"Please wait a few moments and try again.\n"
                    f"If the problem persists, contact support."
                ) from e
            elif "api key" in error_msg or "authentication" in error_msg or "401" in error_msg:
                raise RuntimeError(
                    f"Claude AI authentication failed.\n"
                    f"This is a configuration issue. Please contact your system administrator.\n"
                    f"Technical details: Invalid or missing API key."
                ) from e
            elif "timeout" in error_msg or "timed out" in error_msg:
                raise RuntimeError(
                    f"Claude AI request timed out.\n"
                    f"The AI service is taking longer than expected to respond.\n"
                    f"This usually happens with very large documents or high system load.\n"
                    f"Please try again in a few moments."
                ) from e
            elif "connection" in error_msg or "network" in error_msg:
                raise RuntimeError(
                    f"Cannot connect to Claude AI service.\n"
                    f"There may be a network issue or the service may be temporarily unavailable.\n"
                    f"Please check your internet connection and try again."
                ) from e
            else:
                # Re-raise with original error
                raise

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text, handling markdown code fences.

        Wrapper around LLMClient.extract_json() for convenience.

        Args:
            text: Raw text that may contain JSON

        Returns:
            Extracted JSON string

        Raises:
            ValueError: If no valid JSON found
        """
        return self.llm_client.extract_json(text)

    async def _start_operation(
        self,
        operation_name: str,
        trace_id: str,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **metadata
    ):
        """
        Mark the start of an agent operation.

        Args:
            operation_name: User-friendly operation name (e.g., 'Parse Template: iso9001.docx')
            trace_id: Trace ID for operation tracking
            task_id: Optional task ID
            user_id: Optional user ID
            **metadata: Additional metadata to include in telemetry
        """
        telemetry.agent_started(
            agent_name=self.agent_name,
            trace_id=trace_id,
            task_id=task_id,
            user_id=user_id,
            metadata=metadata
        )

        logger.info(f"{self.agent_name}: Started - {operation_name}")

    async def _complete_operation(
        self,
        operation_name: str,
        trace_id: str,
        task_id: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        **result_summary
    ):
        """
        Mark the completion of an agent operation.

        Args:
            operation_name: User-friendly operation name
            trace_id: Trace ID for operation tracking
            task_id: Optional task ID
            duration_seconds: Operation duration in seconds
            **result_summary: Summary of results (e.g., sections=5, fields=20)
        """
        telemetry.agent_completed(
            agent_name=self.agent_name,
            trace_id=trace_id,
            task_id=task_id,
            duration_seconds=duration_seconds,
            result_summary=result_summary
        )

        logger.info(
            f"{self.agent_name}: Completed - {operation_name} "
            f"({duration_seconds}s)" if duration_seconds else ""
        )

    async def _fail_operation(
        self,
        operation_name: str,
        trace_id: str,
        error: str,
        task_id: Optional[str] = None,
        error_type: str = "agent_error"
    ):
        """
        Mark the failure of an agent operation.

        Args:
            operation_name: User-friendly operation name
            trace_id: Trace ID for operation tracking
            error: Error message
            task_id: Optional task ID
            error_type: Error type for categorization
        """
        telemetry.agent_failed(
            agent_name=self.agent_name,
            trace_id=trace_id,
            task_id=task_id,
            error=error,
            error_type=error_type
        )

        logger.error(f"{self.agent_name}: Failed - {operation_name}: {error}")
