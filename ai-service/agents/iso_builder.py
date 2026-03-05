"""
ISO Builder Agent
=================
Reads an ISO standard PDF and generates:
- A summary (overview, themes, clause/control counts)
- N operational procedure templates (same structure as existing templates)

Uses long-context Gemini model. Prompt loaded from DB ai_prompts table.
"""

import json
import logging
import re
import time
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ISOBuilderAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "ISOBuilderAgent"

    async def build_from_pdf(
        self,
        pdf_path: str,
        prompt_template: str,
        language: str = "en",
        send_as_strategy: str = "extract_text",
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point.
        1. Extract text from PDF
        2. Inject into prompt
        3. Call Gemini
        4. Parse and return structured result
        """
        start = time.time()

        if progress_callback:
            await progress_callback(10, "Extracting PDF text...")

        LANGUAGE_NAMES = {
            "en": "English", "he": "Hebrew", "fr": "French", "de": "German",
            "es": "Spanish", "pt": "Portuguese", "ar": "Arabic", "zh": "Chinese",
            "ja": "Japanese", "ru": "Russian",
        }
        lang_name = LANGUAGE_NAMES.get(language, language)
        lang_instruction = (
            f"\n\nLANGUAGE REQUIREMENT: Generate ALL human-readable text (template names, titles, "
            f"questions, content, descriptions, key_themes, overview) in {lang_name}. "
            f"Keep ALL placeholder keys, automation_source values, trigger_event values, "
            f"semantic_tags, field IDs, and JSON keys in English (lowercase_underscore). "
            f"The JSON structure must remain identical — only the human-readable string values change."
        ) if language != "en" else ""

        if progress_callback:
            await progress_callback(25, "Sending to AI model...")

        if send_as_strategy == "native_pdf":
            logger.info(f"Using native PDF strategy for {pdf_path}")
            if not hasattr(self.llm_client, 'call_with_pdf'):
                logger.warning("Provider does not support native_pdf — falling back to extract_text")
                send_as_strategy = "extract_text"
            else:
                prompt = prompt_template.split("ISO STANDARD TEXT:")[0].strip() + lang_instruction
                result = await self.llm_client.call_with_pdf(
                    pdf_path=pdf_path,
                    prompt=prompt,
                    temperature=0.2,
                )
        if send_as_strategy == "extract_text":
            iso_text = self._extract_pdf_text(pdf_path)
            logger.info(f"Extracted {len(iso_text)} chars from {pdf_path}")
            if len(iso_text.strip()) < 500:
                raise ValueError(
                    f"PDF appears to be image-based (scanned) — extracted only {len(iso_text.strip())} characters. "
                    f"Please provide a text-based PDF. If this is a scanned document, use an OCR tool first."
                )
            prompt = prompt_template.replace("{{ISO_TEXT}}", iso_text) + lang_instruction
            result = await self._call_llm(
                prompt=prompt,
                temperature=0.2,
                trace_id=trace_id,
                task_id=task_id,
                call_purpose="iso_build",
            )

        if progress_callback:
            await progress_callback(80, "Parsing AI response...")

        content = result.get("content", "")
        finish_reason = result.get("finish_reason", "")
        output_tokens = result.get("usage", {}).get("output_tokens", 0)
        logger.info(f"Gemini finish_reason={finish_reason}, output_tokens={output_tokens}, max_tokens={self.max_tokens}")

        if not content or not content.strip():
            raise ValueError(
                f"Gemini returned empty content. finish_reason={finish_reason}, "
                f"output_tokens={output_tokens}, max_tokens={self.max_tokens}"
            )

        if finish_reason == "MAX_TOKENS":
            logger.warning(
                f"Response truncated at MAX_TOKENS ({output_tokens}). "
                f"The ISO standard PDF may be too large. Consider splitting it."
            )

        logger.info(f"Raw Gemini response preview (first 500 chars): {content[:500]}")
        json_str = self._extract_json(content)
        data = self._parse_json_robust(json_str, finish_reason, output_tokens, content)

        duration = int(time.time() - start)
        logger.info(
            f"ISO build complete: {len(data.get('templates', []))} templates, "
            f"{duration}s, ${result.get('cost_usd', 0):.4f}"
        )

        return {
            "summary": data.get("summary", {}),
            "placeholder_dictionary": data.get("placeholder_dictionary", []),
            "templates": data.get("templates", []),
            "cost_usd": result.get("cost_usd", 0),
            "tokens_input": result.get("usage", {}).get("input_tokens", 0),
            "tokens_output": result.get("usage", {}).get("output_tokens", 0),
            "duration_seconds": duration,
            "model": result.get("model", self.model),
        }

    def _parse_json_robust(self, json_str: str, finish_reason: str, output_tokens: int, raw_content: str) -> dict:
        """
        Parse JSON with progressive fallback repair:
        1. Standard json.loads
        2. Regex-fix trailing commas (handles whitespace between comma and closing brace/bracket)
        3. json-repair library (handles single quotes, comments, truncated JSON, etc.)
        """
        # Attempt 1: standard parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Standard JSON parse failed at char {e.pos}: {e.msg}. Attempting repair...")

        # Attempt 2: regex-based trailing comma removal (handles ,\n  } patterns)
        try:
            fixed = re.sub(r',\s*}', '}', json_str)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            logger.warning("Regex trailing-comma fix insufficient. Trying json-repair...")

        # Attempt 3: json-repair library
        try:
            from json_repair import repair_json
            repaired = repair_json(json_str, return_objects=True)
            if isinstance(repaired, dict):
                logger.info("json-repair successfully repaired the JSON.")
                return repaired
        except Exception as repair_err:
            logger.warning(f"json-repair failed: {repair_err}")

        # All attempts failed
        if finish_reason == "MAX_TOKENS":
            raise ValueError(
                f"AI response was truncated mid-JSON (MAX_TOKENS={output_tokens}). "
                f"The ISO standard PDF is too large for a single request. "
                f"Please split the PDF into smaller sections and build each separately."
            )
        logger.error(f"JSON parse failed. Raw content preview: {raw_content[:500]}")
        raise ValueError(
            f"Failed to parse AI response as JSON. "
            f"finish_reason={finish_reason}, output_tokens={output_tokens}. "
            f"The LLM may have produced invalid JSON syntax."
        )

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract plain text from PDF using pypdf."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
            return "\n\n".join(pages)
        except ImportError:
            raise RuntimeError("pypdf not installed. Add 'pypdf' to requirements.txt")
        except Exception as e:
            raise ValueError(f"Failed to read PDF {pdf_path}: {e}")
