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
from google import genai
from google.genai import types as genai_types

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
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
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

                config = genai_types.GenerateContentConfig(
                    system_instruction=system_prompt or None,
                    max_output_tokens=self.max_tokens,
                    temperature=temperature,
                )

                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
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

                try:
                    finish_reason = response.candidates[0].finish_reason.name
                except Exception:
                    finish_reason = "UNKNOWN"

                content = response.text or ""

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
                    "model": self.model_name,
                    "finish_reason": finish_reason
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

    async def call_with_pdf(
        self,
        pdf_path: str,
        prompt: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Upload PDF via Gemini File API and generate with it as native input."""
        logger.info(f"Uploading PDF to Gemini File API: {pdf_path}")
        pdf_file = await self.client.aio.files.upload(
            path=pdf_path,
            config={"mime_type": "application/pdf"},
        )
        logger.info(f"PDF uploaded: {pdf_file.name}")

        config = genai_types.GenerateContentConfig(
            max_output_tokens=self.max_tokens,
            temperature=temperature,
        )

        async with GeminiClient._semaphore:
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    start_time = time.time()
                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=[pdf_file, prompt],
                        config=config,
                    )
                    duration_ms = int((time.time() - start_time) * 1000)

                    try:
                        input_tokens = response.usage_metadata.prompt_token_count
                        output_tokens = response.usage_metadata.candidates_token_count
                        total_tokens = response.usage_metadata.total_token_count
                    except AttributeError:
                        input_tokens = output_tokens = total_tokens = 0

                    try:
                        finish_reason = response.candidates[0].finish_reason.name
                    except Exception:
                        finish_reason = "UNKNOWN"

                    content = response.text or ""

                    # Clean up uploaded file
                    try:
                        await self.client.aio.files.delete(name=pdf_file.name)
                    except Exception:
                        pass

                    return {
                        "content": content,
                        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens},
                        "cost_usd": self._calculate_cost(input_tokens, output_tokens),
                        "duration_ms": duration_ms,
                        "model": self.model_name,
                        "finish_reason": finish_reason,
                    }
                except Exception as e:
                    last_error = e
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            raise RuntimeError(f"Gemini PDF call failed after {self.max_retries} retries: {last_error}")

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
        Robust version that handles all Gemini response formats.
        """
        if not text:
            raise ValueError("Empty response from LLM")

        text = text.strip()

        # Remove markdown code fences (handle ```json, ```JSON, ``` variants)
        for fence in ["```json", "```JSON", "```"]:
            if fence in text:
                start = text.find(fence) + len(fence)
                # Skip newline after fence marker
                if start < len(text) and text[start] == "\n":
                    start += 1
                end = text.find("```", start)
                if end != -1:
                    text = text[start:end].strip()
                    break

        # Find the outermost JSON object
        start = text.find("{")
        if start == -1:
            raise ValueError("No valid JSON found in response")

        # Walk forward tracking brace depth to find matching close
        brace_count = 0
        in_string = False
        escape_next = False
        last_close = -1

        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0:
                    last_close = i
                    break

        if last_close != -1:
            return text[start:last_close + 1]

        # Brace never closed — return from start to end (truncated response)
        logger.warning("JSON appears truncated — returning partial content for repair")
        return text[start:]


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
