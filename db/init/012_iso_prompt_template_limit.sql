-- Add template count limit and grouping guidance to both ISO build prompts

UPDATE dna_app.ai_prompts
SET prompt_text = REPLACE(
    prompt_text,
    '- Group related controls into logical standalone procedure documents',
    '- Generate between 8 and 15 templates total. NEVER exceed 15. If the standard has more topics, consolidate.
- Each template must cover a complete functional area (e.g. Risk Management, Access Control, Incident Response). Do NOT split sub-topics of the same area into separate templates — merge them into one.
- Group related controls into logical standalone procedure documents'
)
WHERE prompt_key IN ('iso_build', 'iso_build_formal');
