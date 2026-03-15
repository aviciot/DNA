"""
Shared LLM Caller
=================
Single entry-point for all LLM calls in the automation service.
Supports: gemini, anthropic (claude), groq, openai.

Returns (text, tokens_input, tokens_output, duration_ms).
"""
import logging
import time as _time

logger = logging.getLogger(__name__)


async def call_llm(
    provider: str,
    model: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    settings=None,
    image_attachments: list | None = None,
) -> tuple:
    """
    Call the specified LLM provider and return (text, tok_in, tok_out, duration_ms).

    provider: "gemini" | "anthropic" | "claude" | "groq" | "openai"
    image_attachments: list of {"mime": str, "content": str (base64)} — only used by vision-capable providers
    """
    # Normalise provider name: "claude" is an alias for "anthropic"
    provider = (provider or "gemini").lower()
    if provider == "claude":
        provider = "anthropic"

    image_attachments = image_attachments or []

    t0 = _time.time()

    if provider == "gemini":
        text, tok_in, tok_out = await _call_gemini(
            api_key=api_key or (getattr(settings, "GOOGLE_API_KEY", "") if settings else ""),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            image_attachments=image_attachments,
        )

    elif provider == "anthropic":
        text, tok_in, tok_out = await _call_anthropic(
            api_key=api_key or (getattr(settings, "ANTHROPIC_API_KEY", "") if settings else ""),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            image_attachments=image_attachments,
        )

    elif provider == "groq":
        text, tok_in, tok_out = await _call_groq(
            api_key=api_key or (getattr(settings, "GROQ_API_KEY", "") if settings else ""),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    else:  # openai
        text, tok_in, tok_out = await _call_openai(
            api_key=api_key or (getattr(settings, "OPENAI_API_KEY", "") if settings else ""),
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    duration_ms = int((_time.time() - t0) * 1000)
    return text, tok_in, tok_out, duration_ms


# ──────────────────────────────────────────────────────────────
# Provider implementations
# ──────────────────────────────────────────────────────────────

async def _call_gemini(api_key, model, system_prompt, user_prompt, temperature, max_tokens, image_attachments) -> tuple:
    from google import genai
    from google.genai import types as genai_types
    import base64

    client = genai.Client(api_key=api_key)
    parts = [user_prompt]
    for att in image_attachments:
        img_bytes = base64.b64decode(att["content"])
        parts.append(genai_types.Part.from_bytes(data=img_bytes, mime_type=att.get("mime", "image/jpeg")))

    resp = await client.aio.models.generate_content(
        model=model,
        contents=parts,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    text = resp.text
    try:
        tok_in  = resp.usage_metadata.prompt_token_count
        tok_out = resp.usage_metadata.candidates_token_count
    except AttributeError:
        tok_in  = len(user_prompt) // 4
        tok_out = len(text) // 4
    return text, tok_in, tok_out


async def _call_anthropic(api_key, model, system_prompt, user_prompt, temperature, max_tokens, image_attachments) -> tuple:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    content = [{"type": "text", "text": user_prompt}]
    for att in image_attachments:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": att["mime"], "data": att["content"]},
        })

    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    text    = msg.content[0].text
    tok_in  = msg.usage.input_tokens
    tok_out = msg.usage.output_tokens
    return text, tok_in, tok_out


async def _call_groq(api_key, model, system_prompt, user_prompt, temperature, max_tokens) -> tuple:
    from groq import AsyncGroq

    client = AsyncGroq(api_key=api_key)
    resp = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    text    = resp.choices[0].message.content
    tok_in  = resp.usage.prompt_tokens     if resp.usage else len(user_prompt) // 4
    tok_out = resp.usage.completion_tokens if resp.usage else len(text) // 4
    return text, tok_in, tok_out


async def _call_openai(api_key, model, system_prompt, user_prompt, temperature, max_tokens) -> tuple:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    resp = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    text    = resp.choices[0].message.content
    tok_in  = resp.usage.prompt_tokens     if resp.usage else len(user_prompt) // 4
    tok_out = resp.usage.completion_tokens if resp.usage else len(text) // 4
    return text, tok_in, tok_out
