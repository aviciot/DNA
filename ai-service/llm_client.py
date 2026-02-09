"""
LLM Client with Rate Limiting
==============================

Thread-safe, rate-limited wrapper for LLM API calls.
Prevents hitting API rate limits when multiple tasks run concurrently.

Features:
- Global rate limiting (max concurrent calls)
- Exponential backoff retry
- Cost calculation
- Token tracking
- Telemetry integration
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic, RateLimitError, APIError

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Rate-limited LLM client for all agents.

    Implements global semaphore to prevent rate limit errors
    when multiple tasks call LLM APIs simultaneously.

    Thread-safe for concurrent use.
    """

    # Class-level semaphore (shared across all instances)
    _semaphore: Optional[asyncio.Semaphore] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        max_concurrent_calls: int = 2,
        max_retries: int = 3
    ):
        """
        Initialize LLM client.

        Args:
            api_key: Anthropic API key
            model: Model to use
            max_tokens: Max tokens per request
            max_concurrent_calls: Max simultaneous API calls (prevents rate limits)
            max_retries: Max retry attempts on failure
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        # Initialize global semaphore (only once)
        if LLMClient._semaphore is None:
            LLMClient._semaphore = asyncio.Semaphore(max_concurrent_calls)

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> Dict[str, Any]:
        """
        Call LLM with rate limiting and retry logic.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0-1)

        Returns:
            {
                "content": "Response text",
                "usage": {
                    "input_tokens": 1234,
                    "output_tokens": 567,
                    "total_tokens": 1801
                },
                "cost_usd": 0.0234,
                "duration_ms": 1234
            }

        Raises:
            APIError: If all retries fail
        """
        async with LLMClient._semaphore:  # Rate limit: wait for available slot
            return await self._call_with_retry(prompt, system_prompt, temperature)

    async def _call_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float
    ) -> Dict[str, Any]:
        """Call LLM with exponential backoff retry."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Build messages
                messages = [{"role": "user", "content": prompt}]

                # Call API
                kwargs = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": temperature,
                    "messages": messages
                }

                if system_prompt:
                    kwargs["system"] = system_prompt

                response = await self.client.messages.create(**kwargs)

                # Calculate metrics
                duration_ms = int((time.time() - start_time) * 1000)
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                cost_usd = self._calculate_cost(input_tokens, output_tokens)

                # Extract text content
                content = response.content[0].text

                logger.debug(
                    f"LLM call successful: {input_tokens} in, {output_tokens} out, "
                    f"{duration_ms}ms, ${cost_usd:.4f}"
                )

                return {
                    "content": content,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens
                    },
                    "cost_usd": cost_usd,
                    "duration_ms": duration_ms,
                    "model": self.model
                }

            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                    raise

            except APIError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"API error: {e}, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"API error after {self.max_retries} attempts: {e}")
                    raise

        # Should never reach here, but just in case
        raise last_error or Exception("LLM call failed")

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost based on token usage.

        Pricing (Claude Sonnet 4.5):
        - Input: $3.00 per 1M tokens
        - Output: $15.00 per 1M tokens
        """
        input_cost = (input_tokens / 1_000_000) * 3.00
        output_cost = (output_tokens / 1_000_000) * 15.00
        return input_cost + output_cost

    def extract_json(self, text: str) -> str:
        """
        Extract JSON from text, handling markdown code fences.

        Handles responses like:
        ```json
        {"key": "value"}
        ```

        Or plain:
        {"key": "value"}

        Args:
            text: Raw text that may contain JSON

        Returns:
            Extracted JSON string

        Raises:
            ValueError: If no valid JSON found
        """
        text = text.strip()

        # Remove markdown code fences
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        # Find JSON object or array
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace == -1 and start_bracket == -1:
            raise ValueError("No JSON object or array found in response")

        # Determine which comes first
        if start_brace == -1:
            start = start_bracket
            end_char = "]"
        elif start_bracket == -1:
            start = start_brace
            end_char = "}"
        else:
            start = min(start_brace, start_bracket)
            end_char = "}" if start == start_brace else "]"

        # Find matching closing bracket
        end = text.rfind(end_char)

        if end == -1 or end < start:
            raise ValueError(f"No matching {end_char} found for JSON")

        json_str = text[start:end + 1]
        return json_str


# Global instance for shared rate limiting
_global_client: Optional[LLMClient] = None


def get_llm_client(
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
    max_concurrent_calls: int = 2
) -> LLMClient:
    """
    Get or create global LLM client.

    Uses singleton pattern to ensure rate limiting is shared
    across all agents and tasks.
    """
    global _global_client

    if _global_client is None:
        _global_client = LLMClient(
            api_key=api_key,
            model=model,
            max_concurrent_calls=max_concurrent_calls
        )

    return _global_client
