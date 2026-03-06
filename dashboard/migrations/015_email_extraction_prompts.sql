-- Migration 015: Add email extraction prompts to ai_prompts table
-- These are the prompts used by the automation-service email_extract_agent.py

INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, model, max_tokens, temperature, description, is_active)
VALUES (
  'email_extraction_system',
  'You are a compliance data extraction assistant.
Your job is to read customer email replies and extract answers to specific compliance questions.
You MUST respond with valid JSON only — no markdown, no explanation outside the JSON.

Two rules for confidence scoring:
1. If the customer clearly and specifically answers a question -> confidence 0.85-1.0 (auto-apply)
2. If the customer provides ANY direct response to a question, even vague or incomplete -> confidence 0.40-0.70 (human review)
   Do NOT silently drop vague answers — extract them with low confidence so a human can decide.

Only omit a question entirely when the email has zero relevant content for it.
If the customer asks a question rather than answering, add its key to follow_up_keys.
Questions marked [ANSWERED] already have an answer on file — only extract if the new answer is different or more specific.',
  'gemini-2.5-flash',
  2048,
  0.10,
  'System prompt for email extraction agent — controls confidence scoring rules and output format',
  true
),
(
  'email_extraction_user',
  E'## Compliance Questions to Answer\n\n{questions_block}\n\n## Evidence / Document Requests\n\n{evidence_block}\n\n## Customer Email Body\n\n{body_text}\n\n## Attachments\n\n{attachments_block}\n\n---\n\nExtract answers and evidence matches. Return ONLY this JSON:\n\n{{\n  "answers": [\n    {{\n      "placeholder_key": "the_key",\n      "value": "extracted answer text",\n      "confidence": 0.95,\n      "reasoning": "Customer stated this directly in paragraph 2"\n    }}\n  ],\n  "evidence_matches": [\n    {{\n      "task_id": "uuid-of-task",\n      "filename": "attached_file.pdf",\n      "confidence": 0.80,\n      "reasoning": "Filename and content matches the requested ISO certificate"\n    }}\n  ],\n  "follow_up_keys": ["key1", "key2"],\n  "notes": "Optional: anything else useful from this email"\n}}\n\nRules:\n- confidence must be between 0.0 and 1.0\n- Only include items you actually found — do not fabricate\n- For questions with no answer in the email, omit them entirely from "answers"\n- For evidence: match by filename AND content description',
  'gemini-2.5-flash',
  2048,
  0.10,
  'User prompt template for email extraction — placeholders: {questions_block}, {evidence_block}, {body_text}, {attachments_block}',
  true
)
ON CONFLICT (prompt_key) DO NOTHING;
