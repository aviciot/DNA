"""
Gemini LLM Client
=================

Client for Google Gemini API with rate limiting.
Supports long context windows (1M tokens) for large documents.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Rate-limited Gemini client for template parsing.

    Features:
    - 1M token context window
    - Rate limiting
    - Cost calculation
    - Compatible interface with LLMClient
    """

    # Class-level semaphore (shared across all instances)
    _semaphore: Optional[asyncio.Semaphore] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        max_tokens: int = 16384,
        max_concurrent_calls: int = 2,
        max_retries: int = 3
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Google Gemini API key
            model: Model to use (default: gemini-3-flash-preview)
            max_tokens: Max output tokens
            max_concurrent_calls: Max simultaneous API calls
            max_retries: Max retry attempts
        """
        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        # Initialize global semaphore (only once)
        if GeminiClient._semaphore is None:
            GeminiClient._semaphore = asyncio.Semaphore(max_concurrent_calls)

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> Dict[str, Any]:
        """
        Call Gemini API with rate limiting.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (prepended to prompt)
            temperature: Sampling temperature (0-2 for Gemini)

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
                "model": "gemini-2.0-flash-exp"
            }
        """
        async with GeminiClient._semaphore:
            return await self._call_with_retry(prompt, system_prompt, temperature)

    async def _call_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float
    ) -> Dict[str, Any]:
        """Call Gemini with exponential backoff retry."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Combine system prompt with user prompt
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"

                # Configure generation
                generation_config = genai.GenerationConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=temperature,
                )

                # Call API (run in executor since it's not async)
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(
                        full_prompt,
                        generation_config=generation_config
                    )
                )

                # Calculate metrics
                duration_ms = int((time.time() - start_time) * 1000)

                # Extract usage stats
                try:
                    input_tokens = response.usage_metadata.prompt_token_count
                    output_tokens = response.usage_metadata.candidates_token_count
                    total_tokens = response.usage_metadata.total_token_count
                except AttributeError:
                    # Fallback if usage metadata not available
                    input_tokens = len(full_prompt) // 4  # Rough estimate
                    output_tokens = len(response.text) // 4
                    total_tokens = input_tokens + output_tokens

                cost_usd = self._calculate_cost(input_tokens, output_tokens)

                # Extract text
                content = response.text

                logger.debug(
                    f"Gemini call successful: {input_tokens} in, {output_tokens} out, "
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
                    "model": self.model_name
                }

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Gemini API error (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Gemini API failed after {self.max_retries} attempts: {e}")

        raise RuntimeError(f"Gemini API failed after {self.max_retries} retries: {last_error}")

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Gemini API call.

        Gemini 2.0 Flash pricing (as of 2024):
        - Input: $0.075 per 1M tokens
        - Output: $0.30 per 1M tokens
        - Context caching: $0.01875 per 1M tokens (cached input)
        """
        input_cost = (input_tokens / 1_000_000) * 0.075
        output_cost = (output_tokens / 1_000_000) * 0.30
        return input_cost + output_cost

    def extract_json(self, text: str) -> str:
        """
        Extract JSON from text, handling markdown code fences.

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

        # Find JSON object
        if text.startswith("{"):
            return text

        # Try to find JSON in text
        start = text.find("{")
        if start != -1:
            # Find matching closing brace
            brace_count = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start:i+1]

        raise ValueError("No valid JSON found in response")


def get_gemini_client(
    api_key: str,
    model: str = "gemini-3-flash-preview",
    max_tokens: int = 16384
) -> GeminiClient:
    """
    Create a new Gemini client.

    Args:
        api_key: Gemini API key
        model: Model to use
        max_tokens: Max output tokens

    Returns:
        GeminiClient instance
    """
    client = GeminiClient(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens
    )
    logger.info(f"Gemini client initialized: {model} (max_tokens={max_tokens})")
    return client
