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

        iso_text = self._extract_pdf_text(pdf_path)
        logger.info(f"Extracted {len(iso_text)} chars from {pdf_path}")

        if len(iso_text.strip()) < 500:
            raise ValueError(
                f"PDF appears to be image-based (scanned) — extracted only {len(iso_text.strip())} characters. "
                f"Please provide a text-based PDF. If this is a scanned document, use an OCR tool first."
            )

        if progress_callback:
            await progress_callback(25, "Sending to AI model...")

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
        if not content or not content.strip():
            raise ValueError(
                f"Gemini returned empty content. "
                f"finish_reason may be MAX_TOKENS. "
                f"output_tokens={result.get('usage', {}).get('output_tokens', 0)}, "
                f"max_tokens={self.max_tokens}"
            )

        logger.info(f"Raw Gemini response preview (first 500 chars): {content[:500]}")
        json_str = self._extract_json(content)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try removing trailing commas
            fixed = json_str.replace(",]", "]").replace(",}", "}")
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                logger.error(f"JSON parse failed. Raw content preview: {content[:500]}")
                raise ValueError(f"Failed to parse AI response as JSON: {e}")

        duration = int(time.time() - start)
        logger.info(
            f"ISO build complete: {len(data.get('templates', []))} templates, "
            f"{duration}s, ${result.get('cost_usd', 0):.4f}"
        )

        return {
            "summary": data.get("summary", {}),
            "templates": data.get("templates", []),
            "cost_usd": result.get("cost_usd", 0),
            "tokens_input": result.get("usage", {}).get("input_tokens", 0),
            "tokens_output": result.get("usage", {}).get("output_tokens", 0),
            "duration_seconds": duration,
            "model": result.get("model", self.model),
        }

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
