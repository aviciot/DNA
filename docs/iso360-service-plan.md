# ISO360 Service — Architecture & Implementation Plan

## Overview

ISO360 is a premium service tier attached to a customer's ISO plan. It transforms DNA from a
compliance data collection tool into a full ongoing compliance management partner.

Where the base service prepares a customer for ISO certification, ISO360 keeps them compliant
after certification — managing recurring activities, collecting ongoing evidence, generating
and maintaining required documents, and ensuring the customer is always audit-ready.

ISO360 is enabled per ISO plan. Each plan independently carries ISO360. A customer with
two ISO plans can have ISO360 on one and not the other.

It also introduces a formal **outbound email system** for non-collection communications
(welcome, announcements, reminders) that sit outside the existing follow-up automation loop.

---

## 1. Non-Followup Task System (foundation for everything below)

### Problem
The current automation system only handles compliance collection tasks with built-in follow-up
loops. There is no mechanism for one-time, non-collection communications (welcome, announcements,
recurring reminders) that still need to be tracked.

### Design Decision: Extend `customer_tasks`, not a new table

All customer interactions — compliance tasks, evidence requests, welcome emails, announcements,
recurring reminders — are represented as `customer_tasks`. This keeps the task table as the
single source of truth for the full customer history.

**New columns on `customer_tasks`:**
```sql
ALTER TABLE dna_app.customer_tasks
  ADD COLUMN requires_followup  BOOLEAN  DEFAULT TRUE,
  -- FALSE = scheduler never generates follow-ups for this task

  ADD COLUMN last_error         TEXT     DEFAULT NULL,
  -- populated on send failure; cleared on success

  ADD COLUMN retry_count        INT      DEFAULT 0,
  -- incremented on each send attempt

  ADD COLUMN source             VARCHAR  DEFAULT 'manual',
  -- 'manual' | 'scheduler' | 'iso360_activation' | 'iso360_onboarding'

  ADD COLUMN source_period      VARCHAR;
  -- dedup guard: prevents duplicate recurring tasks per period
  -- format: '2025' (yearly) | '2025-Q2' (quarterly) | '2025-03' (monthly) | '2025-03-15' (event_based)
```

### Non-followup vs followup — how they relate

| Task type | `requires_followup` | Scheduler picks up? | IMAP reply? |
|---|---|---|---|
| Compliance collection (current) | `TRUE` | Yes | Yes |
| Evidence request (current) | `TRUE` | Yes | Yes |
| Welcome / announcement | `FALSE` | Never | No |
| ISO360 recurring reminder | `FALSE` → flips to `TRUE` after 14 days if unresolved | Eventually | Eventually |

Recurring reminder tasks start as `requires_followup=FALSE` (initial non-intrusive notification).
If still unresolved after 14 days, a scheduler job flips them to `requires_followup=TRUE`
and they enter the standard collection follow-up loop automatically.

### Task types (extended `type` field)
```
'question'            -- existing: compliance placeholder question
'evidence'            -- existing: evidence file request
'notification'        -- new: welcome, announcement, reminder (requires_followup=FALSE)
'iso360_recurring'    -- new: recurring compliance activity (starts FALSE, escalates to TRUE)
'iso360_onboarding'   -- new: additional context tasks shown as "Complete your ISO360 Profile"
```

---

## 2. Operational Log: `task_execution_log`

A separate **operational table** that records every send attempt for any task that involves
outbound communication. Keeps `customer_tasks` clean (business-level) while providing a full
audit trail and retry history.

```
task_execution_log
├── id             UUID PK
├── task_id        UUID → customer_tasks
├── attempt_number INT
├── status         VARCHAR  -- 'attempted' | 'succeeded' | 'failed'
├── email_address  TEXT     -- which address was used
├── error_message  TEXT     -- SMTP error, API error, etc.
├── metadata       JSONB    -- provider used, SMTP response code, LLM model used, etc.
└── attempted_at   TIMESTAMP DEFAULT NOW()
```

**Why separate from `customer_tasks`:**
- A single task may have multiple send attempts — one row per attempt vs one row per task
- Operational detail (SMTP responses, retry history) doesn't belong on a business table
- Enables analytics: delivery rates, failure patterns, provider reliability
- Consistent with existing pattern: `email_inbound_log` for inbound, this for outbound

**Visible in:** Admin → Automation → Outbound Log (alongside existing inbound log)

---

## 3. Welcome Emails — Two Triggers

### Email Content Generation — LLM-driven with frame

All outbound emails use the **same hybrid pattern**:

1. **LLM generates the content** — personalised, context-aware, not rigid wording
2. **Code provides a simple branded HTML shell** — consistent header/footer/button styling only
3. **`ai_prompts` table stores all prompts** — editable by admin without code deployment
4. **Fallback** — if LLM fails, a minimal static message is sent (never block delivery)

Each email type has two rows in `ai_prompts`:

| prompt_key | Purpose |
|---|---|
| `welcome_customer_system` | System prompt: tone, frame, output format (JSON sections) |
| `welcome_customer_user` | User prompt template: `{{customer_name}}`, `{{consultant_name}}`, `{{portal_url}}` |
| `welcome_plan_system` | System prompt for ISO plan welcome |
| `welcome_plan_user` | Variables: `{{iso_code}}`, `{{iso_name}}`, `{{iso_scope}}`, `{{industry}}`, `{{consultant_name}}` |
| `iso360_reminder_system` | System prompt for recurring reminder |
| `iso360_reminder_user` | Variables: `{{iso_code}}`, `{{activity_items}}`, `{{due_date}}`, `{{portal_url}}` |
| `announcement_system` | System prompt: LLM polishes/formats admin's draft |
| `announcement_user` | Variables: `{{admin_draft}}`, `{{customer_name}}`, `{{iso_codes}}` |

### Trigger A: Customer creation → `welcome_customer`
Sent when a customer account is created. Does not require an ISO plan yet.

**Context passed to LLM:** customer name, consultant name, portal URL
**Frame:** warm onboarding tone, brief platform intro, portal access explanation

### Trigger B: ISO plan activated → `welcome_plan`
Sent each time a new ISO plan is assigned and activated on a customer.
Handles multi-plan customers correctly — each plan gets its own welcome.

**Context passed to LLM:** customer name, ISO code/name/scope, industry/description,
consultant name, portal URL, first collection expected in N days
**Frame:** professional + approachable, cover certification journey, email channel, portal AI chat

**Flow:**
```
Customer created
  → INSERT customer_tasks (type='notification', title='Welcome to DNA', requires_followup=FALSE)

ISO plan activated
  → INSERT customer_tasks (type='notification', title='Welcome: ISO 27001', requires_followup=FALSE, plan_id=...)
  → automation service picks up pending notification tasks
  → LLM generates personalised body
  → sends via SMTP
  → task status = 'completed', INSERT task_execution_log (status='succeeded')
  → on failure: task status = 'pending', last_error=..., retry_count++, INSERT task_execution_log (status='failed')
```

---

## 4. ISO360 Service

### What it is
An optional premium service enabled per ISO plan. When activated, ISO360 reads the plan's
placeholder metadata and builds a fully personalised compliance programme for that customer —
recurring tasks, evidence templates, and documents — all derived from the ISO standard the
customer is registered on.

```sql
ALTER TABLE dna_app.customer_iso_plans
  ADD COLUMN iso360_enabled           BOOLEAN   DEFAULT FALSE,
  ADD COLUMN iso360_activated_at      TIMESTAMP,
  ADD COLUMN iso360_annual_month      INT       DEFAULT NULL,  -- NULL = use plan anniversary month
  ADD COLUMN iso360_annual_day        INT       DEFAULT NULL;  -- NULL = use plan anniversary day
```

---

## 5. Placeholder Metadata — The Foundation of ISO360

### Core principle
ISO360 does not use a hardcoded list of documents or activities per ISO standard.
Instead, it reads the **placeholder metadata** that is already generated when an ISO plan
is created. Each placeholder is enriched with three metadata fields that tell ISO360
exactly what to do with it.

This means:
- ISO 27001 and ISO 9001 automatically produce different ISO360 programmes
- Adding a new ISO standard to the platform automatically gives it full ISO360 support
- No manual configuration per standard is needed

### Metadata fields added to each placeholder

**`type`** — what the placeholder represents

| Value | Description |
|---|---|
| `policy` | A governance policy document |
| `procedure` | An operational procedure document |
| `operational_activity` | A recurring operational task |
| `review` | A periodic review activity |
| `record` | An evidence record that must be collected |

**`lifecycle`** — whether the placeholder is static or requires ongoing activity

| Value | Description |
|---|---|
| `static` | Created once, updated only when content changes |
| `recurring` | Must be performed/renewed on a defined schedule |

**`update_frequency`** — how often the placeholder must be executed or renewed

| Value | Description |
|---|---|
| `monthly` | Every month |
| `quarterly` | Every quarter |
| `yearly` | Once per year |
| `event_based` | Triggered by an event, not a schedule |

### Examples

```
placeholder: Access Control Policy
type: policy
lifecycle: static
update_frequency: null

placeholder: User Access Review
type: review
lifecycle: recurring
update_frequency: quarterly

placeholder: Access Review Log
type: record
lifecycle: recurring
update_frequency: quarterly

placeholder: Security Awareness Training
type: operational_activity
lifecycle: recurring
update_frequency: yearly

placeholder: Incident Record
type: record
lifecycle: recurring
update_frequency: event_based
```

### How ISO360 reads this metadata

```
for placeholder in plan_placeholders:

    if lifecycle == static:
        → generate document (policy or procedure)
        → store, no scheduled reminders

    if lifecycle == recurring:
        → create ISO360 task template
        → create ISO360 evidence template (if type == record)
        → schedule reminders based on update_frequency
```

Static placeholders become documents. Recurring placeholders become scheduled tasks
with evidence collection. `event_based` placeholders create tasks that are triggered
manually or by system events (e.g. a new incident), not by the scheduler.

---

## 6. ISO360 Template Layer

### How it works — reusing `customer_documents`

The platform already stores all customer-level document copies in `customer_documents`.
ISO360 reuses this exact table — no new customer-level table needed.

```
iso360_templates (platform level, one per placeholder_key, reusable across standards)
    ↓ admin triggers "Generate ISO360 Templates" in ISO Studio
    ↓ LLM generates steps + evidence fields per recurring placeholder (new keys only)
    ↓ stored in iso360_templates + iso360_template_iso_mapping

Customer activates ISO360
    ↓ iso360_templates copied → customer_documents
      document_type = 'iso360_task_template' | 'iso360_evidence_template' | 'iso360_policy'
      iso360_template_id → iso360_templates
      content JSONB = steps / evidence fields / policy content
      status = 'pending_adjustment'
    ↓ LLM adjustment pass → customer_documents.content updated with personalised steps
    ↓ status = 'ready'
    ↓ scheduler reads next_due_date from customer_documents
    ↓ creates customer_tasks per occurrence when due
    ↓ customer completes → evidence uploaded → customer_profile_data updated
```

Templates are generated once per `placeholder_key` at platform level and reused across
standards. Customer copies live in `customer_documents` alongside all other plan documents.

### New columns on `customer_documents`
```sql
ALTER TABLE dna_app.customer_documents
  ADD COLUMN iso360_template_id UUID REFERENCES dna_app.iso360_templates(id) ON DELETE SET NULL,
  ADD COLUMN next_due_date      DATE,       -- scheduler reads this for recurring types
  ADD COLUMN last_completed_at  TIMESTAMP;
```

### `document_type` values for ISO360 rows
```
'iso360_task_template'      -- recurring activity (review, operational_activity)
'iso360_evidence_template'  -- evidence record template (record)
'iso360_policy'             -- generated policy/procedure document
'iso360_risk_assessment'    -- generated risk assessment
```

### What gets produced per placeholder type

| Placeholder type | `document_type` | Content stored in `content` JSONB |
|---|---|---|
| `policy` | `iso360_policy` | Full generated policy document |
| `procedure` | `iso360_policy` | Full generated procedure document |
| `operational_activity` | `iso360_task_template` | Steps + responsible role + frequency |
| `review` | `iso360_task_template` | Checklist steps + evidence requirement |
| `record` | `iso360_evidence_template` | Evidence fields for upload |

### Task template content example
```json
{
  "title": "User Access Review",
  "frequency": "quarterly",
  "responsible_role": "IT Manager",
  "steps": [
    "Export current user list from Azure AD and Google Workspace",
    "Review permissions against role requirements",
    "Remove or adjust unnecessary access",
    "Document results and obtain approval"
  ],
  "evidence_required": "access_review_log"
}
```

### Evidence template content example
```json
{
  "title": "Access Review Log",
  "fields": [
    { "name": "review_date",        "type": "date", "required": true },
    { "name": "systems_reviewed",   "type": "text", "required": true },
    { "name": "reviewer_name",      "type": "text", "required": true },
    { "name": "issues_found",       "type": "text", "required": false },
    { "name": "corrective_actions", "type": "text", "required": false },
    { "name": "approval_sign_off",  "type": "text", "required": true }
  ]
}
```

---

## 7. Customer Adjustment Pass

### What it is
When ISO360 templates are copied to customer level, the LLM runs an adjustment pass.
This personalises every task and evidence template using the customer's existing answers —
without asking them anything new.

### Inputs to the LLM
- ISO360 task/evidence template (steps, fields, frequency)
- Customer's existing collection answers (systems, size, industry, processes)
- ISO360 onboarding answers (risk appetite, suppliers, employee count, critical processes)

### What gets adjusted

**Tasks:**
- Steps reference the customer's actual systems
  - Template: "Export user list from all systems"
  - Adjusted: "Export user list from Azure AD and Google Workspace"
- Responsible role matched to customer's org structure
- Frequency confirmed or overridden based on customer size and risk profile
  - A 3-person company may have User Access Review downgraded from quarterly to yearly

**Evidence templates:**
- Fields pre-populated where answers already exist
  - Supplier Evaluation Report: supplier names pre-filled from onboarding answers
  - Training Attendance Record: employee names pre-filled if provided
  - Risk Assessment Record: risk domains scoped to customer's industry

**Documents:**
- Generated with customer-specific content — not generic templates with blanks
- Reference their actual systems, processes, and current control state
- Known gaps (pending tasks = controls not yet implemented) are surfaced in the document

### ISO360 Onboarding Tasks
Some adjustments require context not covered by the standard collection flow:
- Risk appetite and business impact values
- Supplier list (names, types, criticality)
- RTO/RPO targets and critical processes

When ISO360 is activated, the system auto-creates a set of **ISO360 Onboarding Tasks**
(`source='iso360_onboarding'`). These appear in the portal as "Complete your ISO360 Profile"
— clearly separated from standard collection tasks.

Document generation and full task adjustment begin once onboarding reaches 70% completion
(configurable). Until then, documents are in "waiting for data" state.

---

## 8. Recurring Task Scheduling

### How the scheduler works

The scheduler runs daily and checks each active ISO360 plan for tasks due based on
their `update_frequency`:

| Frequency | Scheduler logic |
|---|---|
| `monthly` | Due on the same day each month |
| `quarterly` | Due every 3 months from last completion or plan activation |
| `yearly` | Due on plan anniversary month/day (or configured override) |
| `event_based` | Not scheduled — triggered manually or by system event |

**Dedup guard:** `source_period` on `customer_tasks` prevents the same recurring task
from being created twice in the same period.

### What happens when a task comes due

1. Scheduler finds plans where a recurring task is due today (based on frequency + last completion)
2. Checks no task with matching `placeholder_key` + `source_period` already exists (dedup)
3. Creates new `customer_tasks` row:
   `type='iso360_recurring'`, `source='scheduler'`, `source_period='2025-Q2'`,
   `requires_followup=FALSE`, `status='pending'`
4. Creates one summary notification task:
   `type='notification'`, `source='scheduler'` — automation service sends reminder email
   (LLM summarises what activities are due and what evidence is needed)
5. Customer portal immediately shows the new tasks in the "ISO360 Activities" section
6. After 14 days: scheduler flips unresolved tasks to `requires_followup=TRUE`
   → enter standard collection follow-up loop automatically

### Example

Customer completed "User Access Review" in January 2025 (quarterly task).
In April 2025, ISO360 creates a new task: "User Access Review (Q2 2025)".
Portal shows it immediately with the adjusted steps referencing their actual systems.
If unresolved after 14 days → follow-up email is sent.

---

## 9. Document Generation

### Source of truth
Documents are generated from `static` lifecycle placeholders (policies, procedures).
The list is derived directly from the placeholder metadata — not from a hardcoded document list.

### Trigger conditions
1. ISO360 activated + onboarding tasks reach 70% completion → start generation queue
2. Customer completes a significant answer batch (80% of collection tasks) → regenerate affected documents
3. Admin triggers manually ("Regenerate All Documents")
4. Yearly cycle for documents whose source placeholder has `update_frequency: yearly`

### Storage
- Generated as PDF/DOCX in customer storage
- Linked in `documents` table (already exists)
- Visible in portal Documents tab with generation date + "regenerate" option

### What the LLM receives
- All customer profile answers + evidence status
- ISO standard control requirements for this document type
- Customer industry, size, description
- Known gaps (pending tasks = controls not yet implemented)

Output: a complete, organisation-specific document that references the customer's actual
systems, processes, and current control state — not a generic template with blanks.

---

## 10. Risk Assessment

### Based on:
- Customer's existing answers (their controls and processes)
- ISO standard's risk control domains
- ISO360 onboarding answers (risk appetite, business impact)
- Known gaps — pending tasks = controls not yet in place = risks not mitigated
- Customer industry (benchmarks typical threats for their sector)

### Output document sections:
1. Asset identification (derived from profile answers)
2. Threat landscape (LLM, benchmarked by industry)
3. Vulnerability assessment (derived from control gaps)
4. Risk matrix (likelihood × impact)
5. Risk treatment plan (accept/mitigate/transfer for each risk)
6. Residual risk summary

This is typically a 10–20 consultant-hour deliverable. ISO360 generates a solid draft
in minutes, which the consultant reviews and finalises.

---

## 11. Supplier Assessment

ISO 27001 (Annex A.15), ISO 27017 (Clause 7), ISO 9001 (Clause 8.4) all require
third-party/supplier risk management. The supplier module is only activated for ISO standards
whose placeholder metadata includes supplier-related controls.

### Flow:
1. Customer adds suppliers in portal (name, type, criticality) — or pre-filled from onboarding answers
2. System generates a tailored assessment questionnaire per supplier (LLM, based on ISO supplier controls + supplier type + criticality)
3. Questionnaire sent to supplier contact via outbound email OR customer fills it on supplier's behalf in the portal
4. Supplier responses tracked
5. LLM generates supplier assessment report per supplier = audit evidence for third-party controls
6. Summary: supplier risk dashboard (criticality × assessment status)

**New table:**
```
customer_suppliers
├── id                UUID PK
├── customer_id       INT
├── plan_id           UUID
├── name              TEXT
├── type              VARCHAR  -- 'cloud_provider' | 'software' | 'service' | 'hardware' | 'other'
├── criticality       VARCHAR  -- 'critical' | 'high' | 'medium' | 'low'
├── contact_email     TEXT
├── notes             TEXT
├── assessment_status VARCHAR  -- 'not_started' | 'questionnaire_sent' | 'responded' | 'reviewed'
├── assessment_doc_id UUID NULL
└── created_at        TIMESTAMP
```

---

## 12. Killer Features

1. **Certification Readiness Score**
   Real-time score (0–100%) with specific blockers. "You are 78% ready for ISO 27001 audit.
   3 critical gaps remain: Risk Treatment Plan not signed off, 2 supplier assessments pending."
   Visible in portal header and admin dashboard. Updates live as tasks are completed.

2. **Audit Pack — One Click**
   Generates a complete, organised evidence folder: all answered controls, all generated
   documents, all evidence files, organised per ISO annex/clause — ready to hand to an auditor.
   Saves 1–2 days of pre-audit preparation. ZIP download from portal.

3. **Proactive AI Compliance Advisor**
   Portal chat is currently reactive. ISO360 makes it proactive. The AI monitors the customer's
   compliance state and surfaces alerts: "Your Risk Assessment is 11 months old. Your cloud
   provider changed in your last update. Sections 4.2 and 6.1 should be reviewed."
   Delivered as portal notifications + optional email digest.

4. **Change Impact Analysis**
   When a customer updates a compliance answer, the system detects which generated documents
   and which controls are affected, and flags them as "review needed". Customer always knows
   what downstream impact their changes have.

5. **Compliance Calendar**
   Visual calendar in portal: recurring activity due dates, document review dates, supplier
   reassessment dates. Linked directly to tasks — click a date to see what's due and act on it.

6. **Supplier Risk Dashboard**
   Visual grid: suppliers by criticality (rows) × assessment status (columns). Red = critical
   supplier with no assessment. Makes third-party risk instantly scannable for customer and auditor.

7. **Gap Analysis Report**
   Auto-generated at any time: controls where evidence is missing or weak, with recommendations.
   Formatted as a PDF deliverable. Can be shared with internal audit committee or board.

---

## 13. Customer Portal Updates

### New sections (ISO360 only)

| Section | Description |
|---|---|
| ISO360 badge in header | "ISO360 Active" badge when enabled |
| Documents tab | All generated documents — download, view generation date, regenerate |
| Risk Assessment | View/download latest risk assessment, request regeneration |
| Suppliers tab | Add/edit suppliers, view assessment status, send questionnaire |
| Compliance Calendar | Upcoming recurring activities, document reviews |
| Readiness Score | Prominent score with top 3 blockers |
| Audit Pack | One-click generate and download |

### Changes to existing sections
- **Progress tab**: show "ISO360 Activities" separately from standard collection tasks
- **Questions tab**: filter by source (collection / ISO360 onboarding / ISO360 recurring)
- **AI chat**: upgraded to proactive advisor mode when ISO360 is active

---

## 14. Admin Dashboard Updates

### Customer workspace (ISO plan card)
- ISO360 toggle (enable/disable per plan)
- ISO360 onboarding task completion %
- Document generation status per document type
- Manual triggers: "Regenerate Documents", "Send Reminder Now", "Generate Risk Assessment"
- ISO360 settings: reminder month/day, document generation threshold (all stored in `iso360_plan_settings`)

### Admin → ISO Studio → ISO360 Templates tab (new)
Per ISO standard:
- List of all placeholders with their metadata (`type`, `lifecycle`, `update_frequency`)
- Visual split: static placeholders (→ documents) vs recurring placeholders (→ tasks)
- Template generation status per placeholder: `not_generated` | `generated` | `needs_review`
- Manual trigger: "Generate ISO360 Templates" per standard
- Inline edit: admin can adjust LLM-generated steps or evidence fields before they go live
- Reuse indicator: shows if a template is shared across multiple ISO standards

### Outbound email log (Admin → Automation)
- New "Outbound Emails" tab alongside existing inbound log
- Sent welcome/announcement/reminder emails with status
- Compose announcement: select recipients (all / by ISO plan), write content, schedule

---

## 15. Implementation Phases

### Phase 1 — Outbound Email Foundation
- `task_execution_log` table + automation service polling + email sender handler
- New columns on `customer_tasks`: `requires_followup`, `last_error`, `retry_count`, `source`, `source_period`
- Welcome email: customer creation (`welcome_customer`) + plan activation (`welcome_plan`)
- LLM-generated `welcome_plan` body with static fallback
- Admin outbound email log UI

### Phase 2 — ISO360 Activation + Placeholder Metadata
- `iso360_enabled` flag on `customer_iso_plans`
- Placeholder metadata fields: `type`, `lifecycle`, `update_frequency` — added to LLM generation prompt
- ISO360 template layer: task templates + evidence templates generated per ISO standard from metadata
- ISO360 onboarding task set auto-created on activation
- Portal: ISO360 badge, ISO360 Activities section, ISO360 Profile section

### Phase 3 — Recurring Task Scheduling + Reminders
- Scheduler: daily job reads recurring templates, creates due tasks, deduplicates by `source_period`
- Escalation job: flips unresolved tasks to `requires_followup=TRUE` after 14 days
- LLM-generated reminder email summarising due activities
- ISO360 settings panel in admin (reminder day, frequency overrides)

### Phase 4 — Customer Adjustment Pass + Document Generation
- LLM adjustment pass on ISO360 template copy: personalises steps, fields, responsible roles
- Document generation agent per static placeholder
- Generation queue triggered at 70% onboarding completion
- Portal Documents tab + admin document status panel

### Phase 5 — Risk Assessment + Readiness Score + Audit Pack
- Risk assessment agent
- Readiness score calculation engine
- Audit pack generator (ZIP all evidence + documents organised by clause)
- Portal Risk Assessment view, Readiness Score widget, Audit Pack button

### Phase 6 — Supplier Assessment
- `customer_suppliers` table + portal Suppliers tab
- Supplier questionnaire generation + outbound email to supplier
- Supplier risk dashboard
- Supplier assessment report generation

### Phase 7 — Proactive AI + Calendar + Change Impact
- Proactive compliance advisor (portal notifications + email digest)
- Change impact analysis on answer update
- Compliance calendar view

---

## 16. Configuration — DB Tables (no hardcoding)

All prompts, model selection, and ISO360 settings live in the DB.
Nothing ISO360-related is hardcoded in application code.

### `ai_prompts` — all LLM prompt templates

| prompt_key | Purpose |
|---|---|
| `iso_build` | ISO standard build — now includes `type`, `lifecycle`, `update_frequency` rules |
| `iso_build_formal` | Formal variant of ISO build — same metadata rules |
| `iso360_template_system` | System prompt for ISO360 task/evidence template generation |
| `iso360_template_user` | User prompt — variables: `{{placeholder_key}}`, `{{type}}`, `{{update_frequency}}`, `{{iso_clause}}`, `{{category}}`, `{{iso_standard_name}}` |
| `iso360_adjustment_system` | System prompt for customer adjustment pass |
| `iso360_adjustment_user` | Variables: `{{template_steps}}`, `{{evidence_fields}}`, `{{customer_answers}}`, `{{customer_industry}}`, `{{customer_size}}` |
| `iso360_reminder_system` | System prompt for recurring reminder email |
| `iso360_reminder_user` | Variables: `{{iso_code}}`, `{{activity_items}}`, `{{due_date}}`, `{{portal_url}}` |
| `welcome_customer_system` / `welcome_customer_user` | Customer creation welcome |
| `welcome_plan_system` / `welcome_plan_user` | ISO plan activation welcome |
| `announcement_system` / `announcement_user` | Admin broadcast announcement |

All prompts are editable by admin in Admin → AI Config. No code deployment needed to tune them.

### `ai_config` — model + provider selection per service

| service | Purpose |
|---|---|
| `iso_builder` | Provider + model for ISO standard build |
| `iso360_template_builder` | Provider + model for ISO360 task/evidence template generation |
| `iso360_adjustment` | Provider + model for customer adjustment pass (can use cheaper/faster model) |
| `iso360_document` | Provider + model for document generation |
| `iso360_risk_assessment` | Provider + model for risk assessment generation |

### `iso360_plan_settings` — per-plan ISO360 configuration (new table)

Replaces the ISO360 columns on `customer_iso_plans` for settings that may grow over time.

```sql
CREATE TABLE dna_app.iso360_plan_settings (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id                     UUID UNIQUE REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    reminder_month              SMALLINT,          -- NULL = use plan anniversary
    reminder_day                SMALLINT,          -- NULL = use plan anniversary
    onboarding_threshold_pct    INT DEFAULT 70,    -- % onboarding completion to trigger doc generation
    collection_threshold_pct    INT DEFAULT 80,    -- % collection completion to trigger regeneration
    adjustment_pass_done        BOOLEAN DEFAULT FALSE,
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW()
);
```

Visible and editable in Admin → Customer Workspace → ISO360 Settings panel.

---

## 17. Design Decisions

| Question | Decision |
|---|---|
| Non-followup tasks | `requires_followup=FALSE` on `customer_tasks` — single table for all interactions; scheduler ignores them; escalates to `TRUE` after 14 days for recurring tasks |
| Operational logging | Separate `task_execution_log` — per-attempt records with SMTP detail, error messages, retry history; keeps `customer_tasks` clean |
| Welcome email trigger | Two emails: `welcome_customer` on customer creation, `welcome_plan` on plan activation (LLM-generated) |
| ISO360 per plan or customer | Per plan — each plan independently activates ISO360 |
| How ISO360 knows what to do | Placeholder metadata (`type`, `lifecycle`, `update_frequency`) — derived from the ISO standard itself, not hardcoded |
| Same for all ISOs? | No — each ISO standard produces different placeholders with different metadata; ISO360 programme is entirely derived from those |
| Same for all customers? | No — LLM adjustment pass personalises tasks and evidence templates using the customer's existing answers and org profile |
| ISO360 template reuse | Templates stored at `placeholder_key` level — if same key exists across ISO 27001 and ISO 27017, one template is generated and reused by both |
| Customer-level ISO360 storage | ISO360 templates copied into `customer_documents` on activation — same table used for all plan documents; `document_type` distinguishes ISO360 rows; `iso360_template_id` links back to platform template |
| `type` vs `source` on tasks | `type` = what the task is (`iso360_recurring`, `notification`, etc.); `source` = what created it (`scheduler`, `manual`, `iso360_activation`) — never share the same value space |
| Dedup guard | `source_period VARCHAR` on `customer_tasks` — format: '2025' (yearly), '2025-Q2' (quarterly), '2025-03' (monthly), '2025-03-15' (event_based); replaces `source_year INT` which was too coarse for sub-yearly frequencies |
| Template generation trigger | Admin-triggered from ISO Studio → ISO360 Templates tab — not automatic on ISO build; reuse check prevents duplicate LLM calls for same `placeholder_key` across standards |
| Prompts and model config | All in DB (`ai_prompts`, `ai_config`) — never hardcoded; editable by admin without deployment |
| ISO360 plan settings | Dedicated `iso360_plan_settings` table — not columns on `customer_iso_plans`; cleaner as settings grow |
| KYC from existing answers | Yes — existing collection answers are the primary input; ISO360 onboarding tasks fill remaining gaps only |
| Recurring reminder basis | Placeholder `update_frequency` drives scheduling — quarterly, yearly, or event-based per activity |
| Document generation trigger | Configurable threshold in `iso360_plan_settings.onboarding_threshold_pct` (default 70%); also on collection threshold and manual trigger |
| Supplier module activation | Only for ISO standards whose placeholders include supplier-related controls |
| Welcome email language | From `customer_automation_config.preferred_language` |
