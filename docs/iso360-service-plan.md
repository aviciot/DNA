# ISO360 Service — Architecture & Implementation Plan

## Overview

ISO360 is a premium service tier attached to a customer's ISO plan. It transforms DNA from a
compliance data collection tool into a full managed compliance partner — generating the actual
ISO-required deliverables, managing annual obligations, and providing a richer portal experience.

It also introduces a formal **outbound email system** for non-collection communications
(welcome, announcements, reminders) that sit outside the existing follow-up automation loop.

---

## 1. Non-Followup Task System (foundation for everything below)

### Problem
The current automation system only handles compliance collection tasks with built-in follow-up
loops. There is no mechanism for one-time, non-collection communications (welcome, announcements,
annual reminders) that still need to be tracked.

### Design Decision: Extend `customer_tasks`, not a new table

All customer interactions — compliance tasks, evidence requests, welcome emails, announcements,
annual reminders — are represented as `customer_tasks`. This keeps the task table as the single
source of truth for the full customer history.

**New columns on `customer_tasks`:**
```sql
ALTER TABLE dna_app.customer_tasks
  ADD COLUMN requires_followup  BOOLEAN  DEFAULT TRUE,
  -- FALSE = scheduler never generates follow-ups for this task

  ADD COLUMN last_error         TEXT     DEFAULT NULL,
  -- populated on send failure; cleared on success

  ADD COLUMN retry_count        INT      DEFAULT 0;
  -- incremented on each send attempt
```

### Non-followup vs followup — how they relate

| Task type | `requires_followup` | Scheduler picks up? | IMAP reply? |
|---|---|---|---|
| Compliance collection (current) | `TRUE` | Yes | Yes |
| Evidence request (current) | `TRUE` | Yes | Yes |
| Welcome / announcement | `FALSE` | Never | No |
| Annual reminder (ISO360) | `FALSE` → flips to `TRUE` after 14 days if unresolved | Eventually | Eventually |

Annual reminder tasks start as `requires_followup=FALSE` (initial non-intrusive notification).
If still unresolved after 14 days, a scheduler job flips them to `requires_followup=TRUE`
and they enter the standard collection follow-up loop.

### Task types (extended `type` field)
```
'question'       -- existing: compliance placeholder question
'evidence'       -- existing: evidence file request
'notification'   -- new: welcome, announcement, reminder (requires_followup=FALSE)
'iso360_annual'  -- new: annual evidence renewal (starts FALSE, escalates to TRUE)
'iso360_onboarding' -- new: additional context tasks for ISO360 document generation
```

---

## 2. Operational Log: `task_execution_log`

A separate **operational table** that records every send attempt for any task that involves
outbound communication. Keeps `customer_tasks` clean (business-level) while providing full
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

## 2. Welcome Emails — Two Triggers

### Trigger A: Customer creation → `welcome_customer`
Sent when a customer account is created. Does not require an ISO plan yet.

**Content:**
- Welcome to DNA, brief intro to the platform
- Portal link (customer already has a `customer_portal_access` token)
- Consultant contact details
- "Your ISO plan will be set up shortly"

**AI generation:** Static template — no LLM needed here. Customer has no plan context yet,
so there is nothing to personalise beyond name + consultant.

### Trigger B: ISO plan activated → `welcome_plan`
Sent each time a new ISO plan is assigned and activated on a customer.
Handles multi-plan customers correctly — each plan gets its own welcome.

**Content (LLM-generated, personalised):**
- ISO plan name, standard scope, why this standard matters for their industry
- Certification process explained: Collection → Gap Review → Document Generation → Audit
- How the email channel works (reply to any email, AI triages answers + attachments)
- Portal link with explanation of AI chat assistant scoped to their specific ISO plan
- What to expect next (first collection email coming within X days)

**AI generation:** Yes — LLM generates the body using:
- Customer name, industry/description
- ISO standard name, scope, key control areas
- Consultant name
- A structured prompt with required sections
- Returns structured JSON (same pattern as extraction reply agent) rendered into branded HTML
- Static fallback if LLM fails

**Flow:**
```
Customer created
  → INSERT customer_tasks (type='notification', title='Welcome to DNA', requires_followup=FALSE)

ISO plan activated
  → INSERT customer_tasks (type='notification', title='Welcome: ISO 27001', requires_followup=FALSE, plan_id=...)
  → automation service picks up pending notification tasks
  → LLM generates personalised body for welcome_plan
  → sends via SMTP
  → task status = 'completed', INSERT task_execution_log (status='succeeded')
  → on failure: task status = 'pending', last_error=..., retry_count++, INSERT task_execution_log (status='failed')
```

---

## 3. ISO360 Service

### What it is
An optional premium service enabled per ISO plan. Each plan independently carries ISO360.

```sql
ALTER TABLE dna_app.customer_iso_plans
  ADD COLUMN iso360_enabled           BOOLEAN   DEFAULT FALSE,
  ADD COLUMN iso360_activated_at      TIMESTAMP,
  ADD COLUMN iso360_annual_month      INT       DEFAULT NULL,  -- NULL = use plan anniversary month
  ADD COLUMN iso360_annual_day        INT       DEFAULT NULL;  -- NULL = use plan anniversary day
```

---

## 4. How ISO360 Knows What to Do Per Customer

This is the core intelligence question. The answer is that ISO360 is built on three layers
of customer knowledge:

### Layer 1: ISO Standard Metadata (already exists, needs enhancement)
Each `iso_standards` row already has `placeholder_dictionary` (all controls/questions).
We add a `required_documents JSONB` field listing the documents every customer on this
standard must produce:

```json
// iso_standards.required_documents for ISO 27001
[
  { "key": "information_security_policy",   "title": "Information Security Policy",       "annual_review": true  },
  { "key": "risk_assessment_report",         "title": "Risk Assessment Report",            "annual_review": true  },
  { "key": "statement_of_applicability",     "title": "Statement of Applicability (SoA)",  "annual_review": true  },
  { "key": "risk_treatment_plan",            "title": "Risk Treatment Plan",               "annual_review": false },
  { "key": "asset_inventory",                "title": "Asset Inventory",                   "annual_review": true  },
  { "key": "business_continuity_plan",       "title": "Business Continuity Plan",          "annual_review": true  },
  { "key": "supplier_assessment_policy",     "title": "Supplier Assessment Policy",        "annual_review": false },
  { "key": "access_control_policy",          "title": "Access Control Policy",             "annual_review": false },
  { "key": "incident_response_procedure",    "title": "Incident Response Procedure",       "annual_review": false }
]
```

This tells the system: for any ISO 27001 customer with ISO360, generate these 9 documents,
and re-review the ones with `annual_review: true` each year.

### Layer 2: KYC from Existing Answers (no re-asking)
The customer has already answered 30–50 compliance questions through the collection flow.
Those answers live in `customer_profile_data` and `customer_tasks`. They contain rich context:
what systems they use, how they handle data, existing controls, business processes.

ISO360 document generation feeds directly on this data. The LLM receives:
- All answered placeholders for the plan
- Customer description / industry
- ISO standard requirements

**This is a key design principle: ISO360 should never ask customers to answer things they
already answered through the collection flow.**

### Layer 3: ISO360 Onboarding Tasks (additional context for premium docs)
Some documents require deeper context not covered by collection questions:
- Risk assessment needs: threat modeling context, risk appetite, business impact values
- Supplier assessment needs: supplier list (names, types, criticality)
- Business continuity needs: RTO/RPO targets, critical processes list

When ISO360 is enabled on a plan, the system auto-creates a set of
**ISO360 Onboarding Tasks** (`source='iso360_onboarding'`).
These appear in the portal as "Complete your ISO360 Profile" — clearly separated from
standard collection tasks. Until enough are answered, document generation is in
"waiting for data" state. Once a threshold is reached (configurable, e.g. 70%),
document generation queue starts.

---

## 5. Annual Evidence Reminder

### Basis: the customer's own plan templates
The customer's plan already has templates with evidence-required controls
(`customer_tasks WHERE requires_evidence=TRUE`). The system knows exactly which
evidence items were collected and when.

### How it works
**Trigger:** Scheduler job runs daily, finds plans where:
- `iso360_enabled = TRUE`
- Annual reminder month/day = today (or plan anniversary if not configured)
- No annual reminder already sent this calendar year (dedup by `source_year`)

**What happens:**
1. Query all evidence tasks completed for this plan in a previous year
2. Auto-create new `customer_tasks` rows for each evidence item:
   `type='iso360_annual'`, `source='iso360_annual'`, `source_year=current_year`,
   `requires_followup=FALSE`, `status='pending'`
3. Auto-create one summary notification task:
   `type='notification'`, `source='iso360_annual'` — automation service sends reminder email
   (LLM summarises what annual items need renewing)
4. Customer portal immediately shows the new tasks in "Annual Review" section
5. After 14 days: scheduler flips unresolved `iso360_annual` tasks to `requires_followup=TRUE`
   → enter standard collection follow-up loop automatically

**Additional task columns needed:**
```sql
ALTER TABLE dna_app.customer_tasks
  ADD COLUMN source      VARCHAR DEFAULT 'manual',
  -- 'manual' | 'ai_generated' | 'iso360_onboarding' | 'iso360_annual'
  ADD COLUMN source_year INT;   -- dedup guard: prevents creating same annual task twice
```

### Example
Customer completed "Access Control Logs" evidence task in March 2025.
In March 2026, ISO360 creates a new task: "Access Control Logs (Annual Review 2026)".
Portal shows it immediately. If unresolved after 14 days → collection email is sent.

---

## 6. ISO Document Generation

### How the system knows what to generate
From `iso_standards.required_documents` (see Layer 1 above). The system iterates
the required documents list and generates each one using a dedicated LLM agent,
fed with the customer's existing answers + ISO360 onboarding answers.

### Trigger conditions
1. ISO360 enabled + ISO360 onboarding tasks reach 70% completion → start generation queue
2. Customer completes a significant answer batch (80% of collection tasks) → regenerate affected documents
3. Admin triggers manually ("Regenerate All Documents")
4. Annual cycle for documents with `annual_review: true`

### Storage
- Generated as PDF/DOCX in customer storage
- Linked in `documents` table (already exists)
- Visible in portal Documents tab with generation date + "regenerate" option

### What good document generation looks like
LLM receives:
- All customer profile answers + evidence status
- ISO standard control requirements for this document type
- Customer industry, size, description
- Known gaps (pending tasks = controls not yet implemented)

Output: a complete, organisation-specific document — not a generic template with blanks,
but a draft that references their actual systems, processes, and current control state.

---

## 7. Risk Assessment

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

## 8. Supplier Assessment

ISO 27001 (Annex A.15), ISO 27017 (Clause 7), ISO 9001 (Clause 8.4) all require
third-party/supplier risk management.

### Flow:
1. Customer adds suppliers in portal (name, type: cloud/software/service/hardware, criticality)
2. System generates a tailored assessment questionnaire per supplier (LLM, based on ISO supplier controls + supplier type + criticality)
3. Questionnaire sent to supplier contact via `outbound_emails`
   OR customer fills it on supplier's behalf in the portal
4. Supplier responses tracked
5. LLM generates supplier assessment report per supplier = audit evidence for third-party controls
6. Summary: supplier risk dashboard (criticality × assessment status)

**New table:**
```
customer_suppliers
├── id              UUID PK
├── customer_id     INT
├── plan_id         UUID
├── name            TEXT
├── type            VARCHAR  -- 'cloud_provider' | 'software' | 'service' | 'hardware' | 'other'
├── criticality     VARCHAR  -- 'critical' | 'high' | 'medium' | 'low'
├── contact_email   TEXT
├── notes           TEXT
├── assessment_status VARCHAR  -- 'not_started' | 'questionnaire_sent' | 'responded' | 'reviewed'
├── assessment_doc_id UUID NULL  -- link to generated assessment document
└── created_at      TIMESTAMP
```

---

## 9. Killer Features for ISO360

1. **Certification Readiness Score**
   Real-time score (0–100%) with specific blockers. "You are 78% ready for ISO 27001 audit.
   3 critical gaps remain: Risk Treatment Plan not signed off, 2 supplier assessments pending."
   Visible in portal header and admin dashboard. Updates live as tasks are completed.

2. **Audit Pack — One Click**
   Generates a complete, organized evidence folder: all answered controls, all generated
   documents, all evidence files, organised per ISO annex/clause — ready to hand to an auditor.
   This alone saves 1–2 days of pre-audit preparation. ZIP download from portal.

3. **Proactive AI Compliance Advisor**
   Portal chat is currently reactive. ISO360 makes it proactive. The AI monitors the customer's
   state and surfaces alerts: "Your Risk Assessment is 11 months old. Your cloud provider
   changed in your last update. Sections 4.2 and 6.1 should be reviewed."
   Delivered as portal notifications + optional email digest.

4. **Change Impact Analysis**
   When a customer updates a compliance answer, the system detects which generated documents
   and which controls are affected, and flags them as "review needed". Customer always knows
   what downstream impact their changes have.

5. **Continuous Compliance Calendar**
   Visual calendar in portal: evidence renewal dates, document review dates, supplier
   reassessment dates, internal audit window. Linked directly to tasks — click a date
   to see what's due and act on it.

6. **Supplier Risk Dashboard**
   Visual grid: suppliers by criticality (rows) × assessment status (columns). Red = critical
   supplier with no assessment. Makes third-party risk instantly scannable for both customer
   and auditor.

7. **Gap Analysis Report**
   Auto-generated at any time: "Here are 8 controls where your evidence is missing or weak,
   and here is our recommendation for each." Formatted as a PDF deliverable. Can be shared
   with internal audit committee or board.

---

## 10. Customer Portal Updates

### New sections (ISO360 only)

| Section | Description |
|---|---|
| ISO360 badge in header | "ISO360 Active" badge when enabled |
| Documents tab | All generated documents — download, view generation date, regenerate |
| Risk Assessment | View/download latest risk assessment, request regeneration |
| Suppliers tab | Add/edit suppliers, view assessment status, send questionnaire |
| Compliance Calendar | Upcoming evidence renewals, document reviews |
| Readiness Score | Prominent score with top 3 blockers |
| Audit Pack | One-click generate and download |

### Changes to existing sections
- **Progress tab**: show "Annual Review" tasks separately from standard collection tasks
- **Questions tab**: filter by source (collection / annual review / ISO360 onboarding)
- **AI chat**: upgraded to proactive advisor mode when ISO360 is active

---

## 11. Admin Dashboard Updates

### Customer workspace (ISO plan card)
- ISO360 toggle (enable/disable per plan)
- ISO360 onboarding task completion %
- Document generation status per document type
- Manual triggers: "Regenerate Documents", "Send Annual Reminder Now", "Generate Risk Assessment"
- ISO360 settings: reminder month/day, document generation threshold

### Outbound email log (Admin → Automation)
- New "Outbound Emails" tab alongside existing inbound log
- Sent welcome/announcement/reminder emails with status
- Compose announcement: select recipients (all / by ISO plan), write content, schedule

---

## 12. Implementation Phases

### Phase 1 — Outbound Email Foundation
- `outbound_emails` table + automation service polling + email sender handler
- Welcome email: customer creation (`welcome_customer`) + plan activation (`welcome_plan`)
- LLM-generated `welcome_plan` body
- Admin outbound email log UI

### Phase 2 — ISO360 Core + Annual Reminder
- `iso360_enabled` flag on plan, `iso360_onboarding` task set auto-created on activation
- Annual evidence reminder: scheduler + auto-task creation + outbound email + escalation to follow-up
- ISO360 settings panel in admin customer workspace
- Portal: Annual Review task section, ISO360 badge

### Phase 3 — Document Generation
- `required_documents` metadata on `iso_standards`
- LLM document generation agent per document type
- Generation queue on ISO360 onboarding completion
- Portal Documents tab + admin document status panel

### Phase 4 — Risk Assessment + Readiness Score + Audit Pack
- Risk assessment agent
- Readiness score calculation
- Audit pack generator (ZIP all evidence + documents organised by clause)
- Portal Risk Assessment view, Readiness Score widget, Audit Pack button

### Phase 5 — Supplier Assessment
- `customer_suppliers` table + portal Suppliers tab
- Supplier questionnaire generation + outbound email to supplier
- Supplier risk dashboard
- Supplier assessment report generation

### Phase 6 — Proactive AI + Calendar
- Proactive compliance advisor (portal notifications + email digest)
- Change impact analysis on answer update
- Compliance calendar

---

## Answered Design Decisions

| Question | Decision |
|---|---|
| Non-followup tasks | `requires_followup=FALSE` on `customer_tasks` — single table for all interactions; scheduler ignores them; escalates to `TRUE` after 14 days for annual tasks |
| Operational logging | Separate `task_execution_log` table — per-attempt records with SMTP detail, error messages, retry history; keeps `customer_tasks` clean |
| Welcome email trigger | Two emails: `welcome_customer` on customer creation (static), `welcome_plan` on plan activation (LLM-generated) |
| AI for welcome content | Yes — LLM generates `welcome_plan` body; static fallback if LLM fails |
| ISO360 per plan or customer | Per plan — each plan independently activates ISO360 |
| How tailored by ISO | `required_documents` metadata on `iso_standards`; each document generated from ISO-specific prompt + customer answers |
| KYC from existing answers | Yes — existing collection answers are the primary input; ISO360 onboarding tasks fill the remaining gaps |
| Annual reminder basis | Customer's own plan templates — evidence tasks completed in prior years are recreated for annual renewal |
| Supplier questionnaire | Via `outbound_emails` (non-followup); supplier fills form OR customer fills on their behalf in portal |
| Document generation trigger | ISO360 onboarding tasks reach 70% completion; also on 80% collection completion and annual cycle |
| Welcome email language | From `customer_automation_config.preferred_language` |
