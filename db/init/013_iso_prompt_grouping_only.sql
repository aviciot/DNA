-- Replace hard count limit with grouping guidance only

UPDATE dna_app.ai_prompts
SET prompt_text = REPLACE(
    prompt_text,
    '- Generate between 8 and 15 templates total. NEVER exceed 15. If the standard has more topics, consolidate.
- Each template must cover a complete functional area (e.g. Risk Management, Access Control, Incident Response). Do NOT split sub-topics of the same area into separate templates — merge them into one.
- Group related controls into logical standalone procedure documents',
    '- Each template must cover a complete functional area (e.g. Risk Management, Access Control, Incident Response). Do NOT create separate templates for sub-topics that belong to the same area — merge them into one template.
- The number of templates should naturally reflect the number of distinct functional areas in the standard. Do not over-split.
- Group related controls into logical standalone procedure documents'
)
WHERE prompt_key IN ('iso_build', 'iso_build_formal');
