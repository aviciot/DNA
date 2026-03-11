"""
OpenAI-compatible LLM Client
==============================

Handles OpenAI and Groq (OpenAI-compatible API) providers.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class OpenAIClient:
    """Rate-limited LLM client for OpenAI and Groq."""

    _semaphore: Optional[asyncio.Semaphore] = None

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        max_concurrent_calls: int = 2,
        max_retries: int = 3,
        base_url: Optional[str] = None,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        if OpenAIClient._semaphore is None:
            OpenAIClient._semaphore = asyncio.Semaphore(max_concurrent_calls)

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
    ) -> Dict[str, Any]:
        async with OpenAIClient._semaphore:
            return await self._call_with_retry(prompt, system_prompt, temperature)

    async def _call_with_retry(self, prompt, system_prompt, temperature):
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=self.max_tokens,
                    temperature=temperature,
                )

                duration_ms = int((time.time() - start_time) * 1000)
                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                content = response.choices[0].message.content or ""

                return {
                    "content": content,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    "cost_usd": 0.0,
                    "duration_ms": duration_ms,
                    "model": self.model,
                }

            except Exception as e:
                last_error = e
                status = getattr(e, "status_code", None)
                is_transient = status in (502, 503, 529)
                if is_transient and attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise last_error or Exception("OpenAI call failed")

    def extract_json(self, text: str) -> str:
        """Reuse same JSON extraction logic as LLMClient."""
        from llm_client import LLMClient
        return LLMClient.extract_json(LLMClient, text)


def get_openai_client(api_key: str, model: str, max_tokens: int = 4096, groq: bool = False) -> OpenAIClient:
    return OpenAIClient(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        base_url=GROQ_BASE_URL if groq else None,
    )
