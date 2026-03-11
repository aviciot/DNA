-- Migration 023: ISO360 Template Layer
-- Enriches placeholder_dictionary with type/lifecycle/update_frequency metadata.
-- Creates iso360_templates + iso360_plan_settings tables.
-- Extends customer_documents for ISO360 customer copies.
-- Updates iso_build prompts to include metadata field rules.

-- ── Backups ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dna_app._backup_iso_standards_023 AS
SELECT * FROM dna_app.iso_standards;

CREATE TABLE IF NOT EXISTS dna_app._backup_customer_tasks_023 AS
SELECT * FROM dna_app.customer_tasks;

-- ── customer_tasks: source_year → source_period (VARCHAR) ────────
-- New format supports sub-yearly dedup:
--   yearly:    '2025'
--   quarterly: '2025-Q2'
--   monthly:   '2025-03'
--   event:     '2025-03-15'
ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS source_period VARCHAR;

UPDATE dna_app.customer_tasks
SET source_period = source_year::TEXT
WHERE source_year IS NOT NULL
  AND source_period IS NULL;

ALTER TABLE dna_app.customer_tasks
    DROP COLUMN IF EXISTS source_year;

-- ── customer_tasks: normalise source value ───────────────────────
UPDATE dna_app.customer_tasks
SET source = 'scheduler'
WHERE source = 'iso360_annual';

-- ── customer_iso_plans: iso360_template_status ───────────────────
-- Tracks which ISO360 templates have been copied to this plan.
ALTER TABLE dna_app.customer_iso_plans
    ADD COLUMN IF NOT EXISTS iso360_template_status JSONB DEFAULT '{}'::jsonb;

-- ── iso360_plan_settings ─────────────────────────────────────────
-- Per-plan ISO360 configuration. Auto-created when ISO360 is enabled.
CREATE TABLE IF NOT EXISTS dna_app.iso360_plan_settings (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id                  UUID UNIQUE REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    reminder_month           SMALLINT CHECK (reminder_month BETWEEN 1 AND 12),
    reminder_day             SMALLINT CHECK (reminder_day BETWEEN 1 AND 31),
    onboarding_threshold_pct INT DEFAULT 70,   -- % onboarding to trigger doc generation
    collection_threshold_pct INT DEFAULT 80,   -- % collection to trigger regeneration
    adjustment_pass_done     BOOLEAN DEFAULT FALSE,
    created_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Backfill: create settings row for plans that already have ISO360 enabled
INSERT INTO dna_app.iso360_plan_settings (plan_id, reminder_month, reminder_day)
SELECT id, iso360_annual_month, iso360_annual_day
FROM dna_app.customer_iso_plans
WHERE iso360_enabled = TRUE
ON CONFLICT (plan_id) DO NOTHING;

-- ── iso360_templates (platform-level, one per placeholder_key) ───
CREATE TABLE IF NOT EXISTS dna_app.iso360_templates (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    placeholder_key  VARCHAR NOT NULL UNIQUE,
    type             VARCHAR NOT NULL CHECK (type IN ('review', 'operational_activity', 'record')),
    update_frequency VARCHAR NOT NULL CHECK (update_frequency IN ('monthly', 'quarterly', 'yearly', 'event_based')),
    title            TEXT NOT NULL,
    responsible_role TEXT,
    steps            JSONB DEFAULT '[]'::jsonb,        -- [{order, instruction}]
    evidence_fields  JSONB DEFAULT '[]'::jsonb,        -- [{field_name, field_type, required}]
    status           VARCHAR DEFAULT 'generated'
                         CHECK (status IN ('generated', 'needs_review', 'approved')),
    generated_by     VARCHAR DEFAULT 'llm'
                         CHECK (generated_by IN ('llm', 'manual')),
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Maps templates to the ISO standards they apply to (many-to-many)
CREATE TABLE IF NOT EXISTS dna_app.iso360_template_iso_mapping (
    template_id     UUID REFERENCES dna_app.iso360_templates(id) ON DELETE CASCADE,
    iso_standard_id UUID REFERENCES dna_app.iso_standards(id) ON DELETE CASCADE,
    covered_clauses TEXT[] DEFAULT '{}',
    PRIMARY KEY (template_id, iso_standard_id)
);

CREATE INDEX IF NOT EXISTS idx_iso360_template_mapping_standard
    ON dna_app.iso360_template_iso_mapping (iso_standard_id);

-- ── customer_documents: ISO360 columns ──────────────────────────
ALTER TABLE dna_app.customer_documents
    ADD COLUMN IF NOT EXISTS iso360_template_id UUID
        REFERENCES dna_app.iso360_templates(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS next_due_date       DATE,
    ADD COLUMN IF NOT EXISTS last_completed_at   TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_customer_documents_iso360_due
    ON dna_app.customer_documents (next_due_date)
    WHERE iso360_template_id IS NOT NULL;

-- ── ai_prompts: update iso_build prompts with ISO360 metadata rules ─
-- Inserts the three new required fields BEFORE the "ISO STANDARD TEXT:" marker so
-- that the native_pdf strategy (which does split("ISO STANDARD TEXT:")[0]) still
-- includes the ISO360 instructions in the prompt sent to the LLM.
UPDATE dna_app.ai_prompts
SET prompt_text = replace(
    prompt_text,
    'ISO STANDARD TEXT:',
    E'--- ISO360 METADATA FIELDS (REQUIRED ON EVERY PLACEHOLDER) ---\n\nFor EVERY entry in the placeholder_dictionary array, you MUST include these three additional fields:\n\n"type" — one of: "policy" | "procedure" | "operational_activity" | "review" | "record"\n  policy              = a governance policy document\n  procedure           = an operational procedure document\n  operational_activity = a recurring operational task (training, patching, monitoring, backups)\n  review              = a periodic review activity (access review, management review, internal audit)\n  record              = an evidence record that must be collected and maintained\n\n"lifecycle" — one of: "static" | "recurring"\n  RULE: policy and procedure are ALWAYS static\n  RULE: operational_activity, review, record are ALWAYS recurring\n\n"update_frequency" — one of: "monthly" | "quarterly" | "yearly" | "event_based" | null\n  Set ONLY when lifecycle = "recurring". Set to null when lifecycle = "static".\n  monthly      = must be performed every month\n  quarterly    = must be performed every quarter\n  yearly       = must be performed once per year\n  event_based  = triggered by an event (incident, change, new access request) — not scheduled\n\nExample entry with all required fields:\n{\n  "key": "user_access_review",\n  "question": "...",\n  "label": "User Access Review",\n  "category": "Access Control",\n  "hint": "...",\n  "data_type": "text",\n  "is_required": true,\n  "type": "review",\n  "lifecycle": "recurring",\n  "update_frequency": "quarterly"\n}\n\nThese three fields (type, lifecycle, update_frequency) are REQUIRED on every entry. Never omit them.\n\nISO STANDARD TEXT:'
)
WHERE prompt_key IN ('iso_build', 'iso_build_formal');

-- ── ai_prompts: new ISO360 prompt rows ──────────────────────────
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, is_active) VALUES
(
  'iso360_template_system',
  'You are an ISO compliance expert. Generate a structured task template for a recurring compliance activity. Output ONLY valid JSON — no markdown fences, no explanation. Use this exact structure:
{
  "title": "string — clear action-oriented name for the activity",
  "responsible_role": "string — job title of the person responsible",
  "steps": [
    {"order": 1, "instruction": "string — concrete, actionable step"}
  ],
  "evidence_fields": [
    {"field_name": "snake_case_name", "field_type": "text|date|number|file|boolean", "required": true}
  ]
}
Generate 3–6 concrete steps. Evidence fields must match what an ISO auditor expects as proof of completion. Be specific and practical. Do not use placeholder text, square brackets, or generic instructions.',
  true
),
(
  'iso360_template_user',
  'Generate an ISO360 task template for the following compliance requirement:

placeholder_key: {{placeholder_key}}
type: {{type}}
update_frequency: {{update_frequency}}
iso_clause: {{iso_clause}}
category: {{category}}
iso_standard: {{iso_standard_name}}

Return only the JSON template — no explanation, no markdown.',
  true
),
(
  'iso360_adjustment_system',
  'You are an ISO compliance expert personalising task templates for a specific organisation. Given a template, adjust the steps and evidence fields to reference the customer''s actual systems, tools, and processes. Output ONLY valid JSON with the same structure as the input. Rules: replace generic terms ("all systems", "your CRM") with specifics from the customer context; adjust the responsible_role to match their org structure; if the company is small (<10 people), simplify or consolidate steps where reasonable. Do not add or remove top-level keys.',
  true
),
(
  'iso360_adjustment_user',
  'Personalise this compliance task template for the organisation described below.

Template steps:
{{template_steps}}

Evidence fields:
{{evidence_fields}}

Organisation context (systems, processes, tools):
{{customer_answers}}

Industry: {{customer_industry}}
Company size: {{customer_size}}

Return only the adjusted JSON with the same structure — no explanation.',
  true
)
ON CONFLICT (prompt_key) DO NOTHING;

-- ── ai_config: new ISO360 service rows ──────────────────────────
INSERT INTO dna_app.ai_config (service, provider, model) VALUES
  ('iso360_template_builder', 'gemini', 'gemini-2.5-flash'),
  ('iso360_adjustment',       'gemini', 'gemini-2.5-flash')
ON CONFLICT (service) DO NOTHING;
