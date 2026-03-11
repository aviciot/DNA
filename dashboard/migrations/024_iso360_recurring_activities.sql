-- Migration 024: ISO360 Recurring Activities
-- Replaces placeholder_dictionary filtering with a dedicated recurring_activities
-- list generated per template (and cross-cutting at ISO level) by the build LLM.

-- ── Schema changes ─────────────────────────────────────────────────────────

ALTER TABLE dna_app.templates
    ADD COLUMN IF NOT EXISTS recurring_activities JSONB DEFAULT '[]'::JSONB;

ALTER TABLE dna_app.iso_standards
    ADD COLUMN IF NOT EXISTS iso360_recurring_activities JSONB DEFAULT '[]'::JSONB;

-- ── Update ai_prompts ──────────────────────────────────────────────────────
-- Insert recurring_activities instructions before "ISO STANDARD TEXT:" marker
-- so both extract_text and native_pdf strategies include them in the prompt.

UPDATE dna_app.ai_prompts
SET prompt_text = replace(
    prompt_text,
    'ISO STANDARD TEXT:',
    E'--- ISO360 RECURRING ACTIVITIES (REQUIRED) ---\n\nFor EVERY template in the "templates" array, add a "recurring_activities" array listing the compliance activities that must be performed regularly for that template\'s functional area.\n\nAdditionally, add a top-level "iso_recurring_activities" array for cross-cutting activities that span all templates (e.g. management review, internal audit, risk assessment cycle).\n\nEach activity object:\n{\n  "key": "globally_unique_lowercase_underscore",\n  "title": "Action-oriented activity name",\n  "iso_clause": "Exact clause or control ref e.g. 9.2 or A.8.2",\n  "type": "review" | "operational_activity" | "record",\n  "update_frequency": "monthly" | "quarterly" | "yearly" | "event_based",\n  "description": "One sentence — what must be done and why it satisfies the clause",\n  "related_placeholder_keys": ["keys from placeholder_dictionary that capture evidence"]\n}\n\nRULES:\n- Activities MUST derive from actual clauses/controls in the standard — no invented activities\n- Each activity MUST include a real iso_clause reference\n- Do NOT include document metadata fields (version, approved_by, effective_date, prepared_by, reviewed_by, document_id) as activities — these are document scaffolding, not compliance activities\n- related_placeholder_keys MUST reference actual keys from placeholder_dictionary\n- Aim for 2–5 activities per template; 2–4 entries in iso_recurring_activities\n- Keys must be globally unique across all activities and iso_recurring_activities\n\nUpdated JSON structure (add these fields to the existing schema):\n{\n  "summary": {"...": "existing fields unchanged"},\n  "placeholder_dictionary": ["...existing..."],\n  "iso_recurring_activities": [\n    {\n      "key": "internal_isms_audit",\n      "title": "Annual Internal ISMS Audit",\n      "iso_clause": "9.2",\n      "type": "review",\n      "update_frequency": "yearly",\n      "description": "Conduct planned internal audits to verify ISMS conformance and effectiveness",\n      "related_placeholder_keys": ["internal_audit_programme"]\n    }\n  ],\n  "templates": [\n    {\n      "name": "...",\n      "covered_clauses": ["..."],\n      "covered_controls": ["..."],\n      "fixed_sections": ["..."],\n      "recurring_activities": [\n        {\n          "key": "user_access_review",\n          "title": "Quarterly User Access Review",\n          "iso_clause": "A.8.2",\n          "type": "review",\n          "update_frequency": "quarterly",\n          "description": "Verify all user access rights remain appropriate and authorized",\n          "related_placeholder_keys": ["access_review_results", "reviewed_by"]\n        }\n      ]\n    }\n  ]\n}\n\nISO STANDARD TEXT:'
)
WHERE prompt_key IN ('iso_build', 'iso_build_formal');

-- Update the user prompt template to include description and activity title context
UPDATE dna_app.ai_prompts
SET prompt_text = 'Generate an ISO360 task template for the following compliance requirement:

activity_key: {{placeholder_key}}
activity_title: {{placeholder_key}}
type: {{type}}
update_frequency: {{update_frequency}}
iso_clause: {{iso_clause}}
template_area: {{category}}
iso_standard: {{iso_standard_name}}
description: {{description}}

Return only the JSON template — no explanation, no markdown.'
WHERE prompt_key = 'iso360_template_user';
