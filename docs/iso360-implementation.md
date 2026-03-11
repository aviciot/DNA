# ISO360 Implementation Tracker
Branch: `feature/iso360`
Plan reference: `docs/iso360-service-plan.md`

---

## Backup Policy (applies to every phase)

Before any migration that modifies or drops existing data, create a backup table:

```sql
-- Pattern: always run this BEFORE the migration
CREATE TABLE dna_app._backup_<table>_<migration_number> AS
SELECT * FROM dna_app.<table>;
```

**When to create a backup:**
- Before any ALTER TABLE that removes or renames a column
- Before any UPDATE that changes existing rows at scale (e.g. populating a new column)
- Before any DROP TABLE
- Before rebuilding an ISO standard (LLM re-run overwrites `placeholder_dictionary`)

**Backup tables are never dropped automatically.** Remove manually once the phase is
validated and stable. If rollback is needed, restore with:

```sql
-- Restore pattern
INSERT INTO dna_app.<table>
SELECT * FROM dna_app._backup_<table>_<migration_number>
ON CONFLICT DO NOTHING;
```

---

## Phase 1 — Non-Followup Task System + Welcome Email
**Status: ✅ Complete**

### DB Changes
- [x] Migration `020`: Add `requires_followup BOOLEAN DEFAULT TRUE` to `customer_tasks`
- [x] Migration `020`: Add `last_error TEXT`, `retry_count INT DEFAULT 0` to `customer_tasks`
- [x] Migration `020`: Add `source VARCHAR DEFAULT 'manual'`, `source_period VARCHAR` to `customer_tasks`
  - `source` values: `'manual'` | `'scheduler'` | `'iso360_activation'` | `'iso360_onboarding'`
  - `source_period` format: `'2025'` (yearly) | `'2025-Q2'` (quarterly) | `'2025-03'` (monthly) | `'2025-03-15'` (event_based)
- [x] Migration `020`: Seed `ai_prompts` rows for all outbound email types:
  - `welcome_customer_system` / `welcome_customer_user`
  - `welcome_plan_system` / `welcome_plan_user`
  - `iso360_reminder_system` / `iso360_reminder_user`
  - `announcement_system` / `announcement_user`
- [x] Migration `021`: Create `task_execution_log` table

### Backend
- [x] `customer_tasks` task types extended: `'notification'` added as valid type
- [x] Scheduler: add `AND requires_followup = TRUE` filter on all follow-up queries
- [x] `iso_customers.py`: on customer create → insert `type='notification'` task (`welcome_customer`)
- [x] `iso_customers.py`: on plan activate → insert `type='notification'` task (`welcome_plan`)
- [x] New route: `POST /api/v1/notifications/broadcast` — admin creates announcement for all/filtered customers

### Automation Service
- [x] New handler: process `type='notification'` pending tasks (separate from collection handler)
- [x] Fetch prompt from `ai_prompts` by `prompt_key` — LLM generates email body (JSON sections → HTML shell)
- [x] Both welcome types use LLM with appropriate prompt key; fallback to minimal static message if LLM fails
- [x] On send success: task `status='completed'`, INSERT `task_execution_log (status='succeeded')`
- [x] On failure: task `last_error=...`, `retry_count++`, INSERT `task_execution_log (status='failed')`
- [x] Retry: re-attempt failed notification tasks up to 3 times before marking `status='failed'`

### Frontend — Admin
- [x] Admin → Automation: new "Outbound" tab — shows `type='notification'` tasks with send status
- [x] Compose announcement: write draft, select recipients (all / by ISO plan), schedule
- [x] Admin → AI Config: edit `welcome_*` / `announcement_*` prompts in `ai_prompts` table

### Frontend — Customer Workspace
- [x] Tasks tab: notification tasks visible in history (non-interactive, read-only, distinct style)

---

## Phase 2 — ISO360 Service Flag + Recurring Reminder
**Status: ✅ Complete (with known issues — see below)**

### DB Changes
- [x] Migration `022`: Add `iso360_enabled`, `iso360_activated_at`, `iso360_annual_month`, `iso360_annual_day` to `customer_iso_plans`
- [x] Migration `022`: Add `required_documents JSONB` to `iso_standards` — **superseded by Phase 3** (placeholder metadata replaces this; do not populate further)

### Backend
- [x] ISO plan API: support `iso360_enabled` toggle (`PATCH /iso-plans/{id}/iso360`)
- [x] On ISO360 enable: auto-create ISO360 onboarding tasks (`source='iso360_onboarding'`, `requires_followup=FALSE`)

### Automation Service / Scheduler
- [x] New scheduler job: daily check for plans where reminder is due
- [x] Reminder job: auto-create evidence tasks (`type='iso360_annual'`, `source_year=year`, `requires_followup=FALSE`)
- [x] Reminder job: insert `type='notification'` task — LLM generates reminder email body
- [x] Escalation job: after 14 days flip unresolved tasks to `requires_followup=TRUE`

### Frontend — Admin
- [x] ISO plan card: ISO360 toggle (enable/disable)
- [x] ISO360 settings: configure reminder month/day
- [x] Manual trigger: "Send Annual Reminder Now"

### Frontend — Customer Portal
- [x] Tasks tab: "Annual Review" section for `source='iso360_annual'` tasks
- [x] ISO360 badge in portal header when plan has ISO360 active

### ⚠️ Known Issues — Fix in Phase 3
- `type='iso360_annual'` → rename to `type='iso360_recurring'` (not everything is annual — some tasks are quarterly)
- Scheduler currently uses anniversary date only → replace with `update_frequency` from placeholder metadata once Phase 3 is complete
- `required_documents` on `iso_standards` is populated but will not be used — placeholder metadata is the source of truth going forward

---

## Phase 3 — Placeholder Metadata + ISO360 Template Layer
**Status: 🔲 Not started**

This is the foundation for all ISO360 operational logic. The placeholder dictionary
already exists and is populated by the LLM. This phase enriches it with three new
fields (`type`, `lifecycle`, `update_frequency`) that tell ISO360 what to do with
each placeholder — generate a document, create a recurring task, or request evidence.

### Pre-conditions
- Placeholder dictionary redesign is complete ✅ (migrations 008–010, `iso_builder.py`, `stream_consumer.py`, `task_generator_service.py` all done)
- `iso_standards.placeholder_dictionary` is being populated on every ISO build ✅

### Backup — run before anything else
```sql
-- Backup iso_standards before modifying placeholder_dictionary structure
CREATE TABLE dna_app._backup_iso_standards_023 AS
SELECT * FROM dna_app.iso_standards;

-- Backup customer_tasks before renaming iso360_annual type
CREATE TABLE dna_app._backup_customer_tasks_023 AS
SELECT * FROM dna_app.customer_tasks;
```

### DB Changes
- [ ] Migration `023`: No schema change needed — `placeholder_dictionary` is already JSONB.
  The new fields (`type`, `lifecycle`, `update_frequency`) are added inside the JSON entries
  by updating the LLM prompt. Existing rows will be backfilled when standards are rebuilt.
- [ ] Migration `023`: Rename `source_year` → `source_period VARCHAR` on `customer_tasks`:
  ```sql
  ALTER TABLE dna_app.customer_tasks
    RENAME COLUMN source_year TO source_period_old;
  ALTER TABLE dna_app.customer_tasks
    ADD COLUMN source_period VARCHAR;
  -- backfill existing iso360_annual rows
  UPDATE dna_app.customer_tasks
    SET source_period = source_period_old::TEXT
  WHERE source_period_old IS NOT NULL;
  ALTER TABLE dna_app.customer_tasks
    DROP COLUMN source_period_old;
  ```
- [ ] Migration `023`: Rename `source='iso360_annual'` → `source='scheduler'` on existing rows:
  ```sql
  UPDATE dna_app.customer_tasks
    SET source = 'scheduler'
  WHERE source = 'iso360_annual';
  ```
- [ ] Migration `023`: Add `iso360_template_status JSONB DEFAULT '{}'` to `customer_iso_plans`
  — tracks which ISO360 task/evidence templates have been generated per plan

### Prompt Change — `iso_build` and `iso_build_formal`
- [ ] Migration `023`: Update both prompts in `ai_prompts` to add three fields to every
  `placeholder_dictionary` entry:

  ```json
  {
    "key": "user_access_review",
    "question": "...",
    "label": "...",
    "category": "...",
    "type": "review",
    "lifecycle": "recurring",
    "update_frequency": "quarterly"
  }
  ```

  **LLM rules to add to the prompt:**

  `type` — one of: `policy` | `procedure` | `operational_activity` | `review` | `record`

  `lifecycle` — one of: `static` | `recurring`
  - `policy` and `procedure` are always `static`
  - `operational_activity`, `review`, `record` are always `recurring`

  `update_frequency` — one of: `monthly` | `quarterly` | `yearly` | `event_based`
  - Only meaningful when `lifecycle = recurring`
  - `event_based` = triggered by an event (incident, change), not a schedule
  - Set to `null` when `lifecycle = static`

### ISO Standard Rebuild
- [ ] Re-run ISO build for each active standard (27001, 27017, 9001) so `placeholder_dictionary`
  entries get the new fields populated by the LLM
- [ ] Verify output: each entry in `placeholder_dictionary` has `type`, `lifecycle`, `update_frequency`
- [ ] Backup before each rebuild:
  ```sql
  -- Run once per standard before rebuilding
  CREATE TABLE IF NOT EXISTS dna_app._backup_iso_standards_023 AS
  SELECT * FROM dna_app.iso_standards;
  -- (table already created above — skip if exists)
  ```

### DB Config — seed in migration `023`

**`ai_prompts` — new rows:**
```sql
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, is_active) VALUES
  ('iso360_template_system', '<system prompt — tone, rules, JSON output format for steps + evidence fields>', true),
  ('iso360_template_user',   '<user prompt — variables: {{placeholder_key}}, {{type}}, {{update_frequency}}, {{iso_clause}}, {{category}}, {{iso_standard_name}}>', true),
  ('iso360_adjustment_system', '<system prompt — rules for personalising steps using customer answers>', true),
  ('iso360_adjustment_user',   '<user prompt — variables: {{template_steps}}, {{evidence_fields}}, {{customer_answers}}, {{customer_industry}}, {{customer_size}}>', true);
```

**`ai_config` — new rows:**
```sql
INSERT INTO dna_app.ai_config (service, provider, model) VALUES
  ('iso360_template_builder', 'gemini', 'gemini-1.5-pro'),
  ('iso360_adjustment',       'gemini', 'gemini-1.5-flash');  -- cheaper model fine for adjustment
```

**`iso360_plan_settings` — new table:**
```sql
CREATE TABLE dna_app.iso360_plan_settings (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id                  UUID UNIQUE REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    reminder_month           SMALLINT,         -- NULL = use plan anniversary
    reminder_day             SMALLINT,         -- NULL = use plan anniversary
    onboarding_threshold_pct INT DEFAULT 70,   -- % onboarding to trigger doc generation
    collection_threshold_pct INT DEFAULT 80,   -- % collection to trigger regeneration
    adjustment_pass_done     BOOLEAN DEFAULT FALSE,
    created_at               TIMESTAMP DEFAULT NOW(),
    updated_at               TIMESTAMP DEFAULT NOW()
);
```
Row auto-created when ISO360 is enabled on a plan. Settings editable in Admin → Customer Workspace → ISO360 Settings panel.

**`iso360_templates` — new table (platform-level, reusable across standards):**
```sql
CREATE TABLE dna_app.iso360_templates (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    placeholder_key  VARCHAR NOT NULL UNIQUE,  -- one template per key, reused across standards
    type             VARCHAR NOT NULL,          -- 'review'|'operational_activity'|'record'
    update_frequency VARCHAR NOT NULL,          -- 'monthly'|'quarterly'|'yearly'|'event_based'
    title            TEXT NOT NULL,
    responsible_role TEXT,
    steps            JSONB DEFAULT '[]',        -- [{order, instruction}]
    evidence_fields  JSONB DEFAULT '[]',        -- [{field_name, field_type, required}]
    generated_by     VARCHAR DEFAULT 'llm',     -- 'llm'|'manual'
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE dna_app.iso360_template_iso_mapping (
    template_id     UUID REFERENCES dna_app.iso360_templates(id) ON DELETE CASCADE,
    iso_standard_id UUID REFERENCES dna_app.iso_standards(id) ON DELETE CASCADE,
    covered_clauses TEXT[],
    PRIMARY KEY (template_id, iso_standard_id)
);
```

**New columns on `customer_documents` — ISO360 customer-level copies land here:**
```sql
ALTER TABLE dna_app.customer_documents
  ADD COLUMN IF NOT EXISTS iso360_template_id UUID REFERENCES dna_app.iso360_templates(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS next_due_date      DATE,
  ADD COLUMN IF NOT EXISTS last_completed_at  TIMESTAMP;
```
`document_type` values for ISO360 rows: `'iso360_task_template'` | `'iso360_evidence_template'` | `'iso360_policy'` | `'iso360_risk_assessment'`

### ISO360 Template Layer
- [ ] New service: `iso360_template_service.py`
  - Triggered by admin from ISO Studio → ISO360 Templates tab
  - Reads `iso_standards.placeholder_dictionary` for the selected standard
  - For each `lifecycle = static` entry → registers as document to generate (no LLM call now)
  - For each `lifecycle = recurring` entry:
    - Checks if `iso360_templates` row already exists for `placeholder_key`
    - If yes → reuse it, insert into `iso360_template_iso_mapping` only
    - If no → call LLM (`iso360_template_system` / `iso360_template_user` prompts from `ai_prompts`)
      using model from `ai_config` where `service='iso360_template_builder'`
    - Stores result in `iso360_templates` + `iso360_template_iso_mapping`

- [ ] On customer ISO360 activation:
  - Copy all `iso360_templates` linked to the plan's standard → `customer_documents`
    - `document_type` = `'iso360_task_template'` | `'iso360_evidence_template'` | `'iso360_policy'`
    - `iso360_template_id` = source template id
    - `content` = template steps / evidence fields / policy content
    - `status` = `'pending_adjustment'`
    - `next_due_date` = calculated from `update_frequency` + activation date
  - Read threshold from `iso360_plan_settings.onboarding_threshold_pct` (not hardcoded)
  - Mark `iso360_plan_settings.adjustment_pass_done = FALSE`

### Scheduler Fix
- [ ] Rename `_iso360_annual_job` → `_iso360_recurring_job`
- [ ] Read `reminder_month` / `reminder_day` from `iso360_plan_settings`
- [ ] Dedup check uses `placeholder_key` + `source_period` (not `source_year`)
- [ ] `source_period` format per frequency:
  - `yearly` → `'2025'`
  - `quarterly` → `'2025-Q2'`
  - `monthly` → `'2025-03'`
  - `event_based` → skip scheduler
- [ ] `source` on created tasks = `'scheduler'` (not `'iso360_recurring'`)
- [ ] Replace anniversary-date-only logic with `update_frequency`-driven scheduling:
  - `quarterly` → due every 3 months from `customer_documents.last_completed_at`
  - `yearly` → due on anniversary month/day from `iso360_plan_settings`
  - `monthly` → due on same day each month
  - `event_based` → skip scheduler; triggered manually or by system event

### Frontend — Admin → ISO Studio → ISO360 Templates tab (new)
- [ ] Per standard: list all placeholders with `type`, `lifecycle`, `update_frequency`
- [ ] Visual split: static (documents) vs recurring (tasks)
- [ ] Template status per placeholder: `not_generated` | `generated` | `needs_review`
- [ ] Reuse badge: shows if template is shared across multiple ISO standards
- [ ] Manual trigger: "Generate ISO360 Templates" per standard
- [ ] Inline edit: admin can adjust LLM-generated steps or evidence fields

### Frontend — Admin → Customer Workspace
- [ ] ISO360 Settings panel reads/writes `iso360_plan_settings` table

### Frontend — Customer Portal
- [ ] Tasks tab: rename "Annual Review" section → "ISO360 Activities"
- [ ] Filter tasks by `type='iso360_recurring'`

---

## Phase 4 — Customer Adjustment Pass + Document Generation
**Status: 🔲 Not started**

### Backup — run before starting
```sql
CREATE TABLE dna_app._backup_customer_iso_plans_024 AS
SELECT * FROM dna_app.customer_iso_plans;

CREATE TABLE dna_app._backup_customer_documents_024 AS
SELECT * FROM dna_app.customer_documents;
```

### DB Changes
- [ ] Migration `024`: Add `iso360_doc_status JSONB DEFAULT '{}'` to `customer_iso_plans`
  — tracks generation state per document key (`pending` | `generating` | `complete` | `failed`)

### DB Config — seed in migration `024`

**`ai_prompts` — new rows:**
```sql
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, is_active) VALUES
  ('iso360_document_system', '<system prompt — document generation rules, output format>', true),
  ('iso360_document_user',   '<user prompt — variables: {{placeholder_key}}, {{iso_clause}}, {{customer_answers}}, {{known_gaps}}, {{industry}}, {{company_size}}>', true);
```

**`ai_config` — new rows:**
```sql
INSERT INTO dna_app.ai_config (service, provider, model) VALUES
  ('iso360_document', 'gemini', 'gemini-1.5-pro');
```

### AI Service
- [ ] New agent: `iso360_adjustment_agent.py`
  - Prompts loaded from `ai_prompts` (`iso360_adjustment_system` / `iso360_adjustment_user`)
  - Model loaded from `ai_config` where `service='iso360_adjustment'`
  - Input: `customer_documents` rows where `iso360_template_id IS NOT NULL AND status='pending_adjustment'`
    + customer's existing answers + ISO360 onboarding answers
  - Output: updated `content` JSONB with personalised steps + pre-filled evidence fields
  - Sets `status='ready'` and `iso360_plan_settings.adjustment_pass_done=TRUE` on completion
  - Re-triggered when customer updates significant answers

- [ ] New agent: `iso360_document_agent.py`
  - Prompts loaded from `ai_prompts` (`iso360_document_system` / `iso360_document_user`)
  - Model loaded from `ai_config` where `service='iso360_document'`
  - Generates one document per `lifecycle=static` placeholder
  - Stores result in `customer_documents` with `document_type='iso360_policy'`, `storage_path` set
  - Triggered when onboarding reaches `iso360_plan_settings.onboarding_threshold_pct` (default 70%)
  - Re-triggered when collection reaches `iso360_plan_settings.collection_threshold_pct` (default 80%)

- [ ] Document generation queue: process one document at a time, update `iso360_doc_status` per key

### Backend
- [ ] Store generated documents in customer storage + link in `documents` table (already exists)
- [ ] Re-generation trigger: on answer update, check which documents are affected → flag as `review_needed`

### Frontend — Admin
- [ ] ISO360 panel: document generation status per document key with last generated date
- [ ] Manual triggers: "Regenerate All Documents" / per-document "Regenerate"

### Frontend — Customer Portal
- [ ] New "Documents" tab (ISO360 only): list generated documents, download, generation date, regenerate button

---

## Phase 5 — Risk Assessment + Readiness Score + Audit Pack
**Status: 🔲 Not started**

### Backup — run before starting
```sql
CREATE TABLE dna_app._backup_customer_iso_plans_025 AS
SELECT * FROM dna_app.customer_iso_plans;
```

### AI Service
- [ ] `risk_assessment_agent.py` — generates tailored risk assessment from:
  customer answers + ISO risk control domains + ISO360 onboarding answers + known gaps + industry benchmarks
- [ ] Readiness score calculator — % from completed tasks vs total required, with top 3 blockers
- [ ] Audit pack generator — ZIP of all evidence files + documents organised by ISO clause/annex

### Frontend — Admin
- [ ] Readiness score on customer workspace header
- [ ] Manual trigger: "Generate Risk Assessment"

### Frontend — Customer Portal
- [ ] Risk Assessment view (download PDF, request regeneration)
- [ ] Readiness Score widget in portal header with top 3 blockers
- [ ] Audit Pack button ("Download Audit Pack")

---

## Phase 6 — Supplier Assessment
**Status: 🔲 Not started**

### Backup — run before starting
```sql
-- No existing table to back up — new table only
```

### DB Changes
- [ ] Migration `026`: Create `customer_suppliers` table:
  ```sql
  CREATE TABLE dna_app.customer_suppliers (
      id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      customer_id       INT REFERENCES dna_app.customers(id),
      plan_id           UUID REFERENCES dna_app.customer_iso_plans(id),
      name              TEXT NOT NULL,
      type              VARCHAR,   -- 'cloud_provider'|'software'|'service'|'hardware'|'other'
      criticality       VARCHAR,   -- 'critical'|'high'|'medium'|'low'
      contact_email     TEXT,
      notes             TEXT,
      assessment_status VARCHAR DEFAULT 'not_started',
      assessment_doc_id UUID,
      created_at        TIMESTAMP DEFAULT NOW()
  );
  ```

### Backend
- [ ] CRUD endpoints for `customer_suppliers`
- [ ] Supplier questionnaire generation (LLM per supplier type + ISO controls)
- [ ] Send questionnaire via `type='notification'` task to supplier contact email

### Frontend — Customer Portal
- [ ] New "Suppliers" tab (ISO360 only): add/edit suppliers, view assessment status, send questionnaire
- [ ] Supplier risk dashboard: criticality × assessment status grid

---

## Phase 7 — Proactive AI + Compliance Calendar + Change Impact
**Status: 🔲 Not started**

- [ ] Proactive compliance advisor: monitors customer state, surfaces alerts in portal + email digest
  ("Your Risk Assessment is 11 months old. Sections 4.2 and 6.1 should be reviewed.")
- [ ] Change impact analysis: when answer updated → detect affected documents → flag as "review needed"
- [ ] Compliance calendar: visual calendar of upcoming recurring activities, linked directly to tasks

---

## Progress Log

| Date | Phase | What was done |
|---|---|---|
| 2026-03-10 | Setup | Branch created, DB dumped, plan finalised |
| 2026-03-10 | Phase 1 | Migrations 020/021 applied; notification_email_agent; scheduler._notification_job; send_notification_email; outbound log + broadcast UI in AutomationConfig.tsx |
| 2026-03-10 | Phase 2 | Migration 022 (iso360 columns + required_documents); PATCH /iso-plans/{id}/iso360; ISOPlanResponse updated; scheduler._iso360_annual_job; ISO360 toggle button in customer workspace |
| 2026-07-10 | Review | Placeholder dictionary redesign confirmed complete (migrations 008–010, iso_builder.py, stream_consumer.py, task_generator_service.py). Phase 3 redefined as placeholder metadata enrichment + ISO360 template layer. required_documents approach superseded. |
