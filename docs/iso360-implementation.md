# ISO360 Implementation Tracker
Branch: `feature/iso360`
Plan reference: `docs/iso360-service-plan.md`

---

## Phase 1 — Non-Followup Task System + Welcome Email
**Status: 🔲 Not started**

### DB Changes
- [ ] Migration `020`: Add `requires_followup BOOLEAN DEFAULT TRUE` to `customer_tasks`
- [ ] Migration `020`: Add `last_error TEXT`, `retry_count INT DEFAULT 0` to `customer_tasks`
- [ ] Migration `020`: Add `source VARCHAR DEFAULT 'manual'`, `source_year INT` to `customer_tasks`
- [ ] Migration `020`: Seed `ai_prompts` rows for all outbound email types:
  - `welcome_customer_system` / `welcome_customer_user`
  - `welcome_plan_system` / `welcome_plan_user`
  - `iso360_reminder_system` / `iso360_reminder_user`
  - `announcement_system` / `announcement_user`
- [ ] Migration `021`: Create `task_execution_log` table

### Backend
- [ ] `customer_tasks` task types extended: `'notification'` added as valid type
- [ ] Scheduler: add `AND requires_followup = TRUE` filter on all follow-up queries
- [ ] `iso_customers.py`: on customer create → insert `type='notification'` task (`welcome_customer`)
- [ ] `iso_customers.py`: on plan activate → insert `type='notification'` task (`welcome_plan`)
- [ ] New route: `POST /api/v1/notifications/broadcast` — admin creates announcement for all/filtered customers

### Automation Service
- [ ] New handler: process `type='notification'` pending tasks (separate from collection handler)
- [ ] Fetch prompt from `ai_prompts` by `prompt_key` — LLM generates email body (JSON sections → HTML shell)
- [ ] Both welcome types use LLM with appropriate prompt key; fallback to minimal static message if LLM fails
- [ ] On send success: task `status='completed'`, INSERT `task_execution_log (status='succeeded')`
- [ ] On failure: task `last_error=...`, `retry_count++`, INSERT `task_execution_log (status='failed')`
- [ ] Retry: re-attempt failed notification tasks up to 3 times before marking `status='failed'`

### Frontend — Admin
- [ ] Admin → Automation: new "Outbound" tab — shows `type='notification'` tasks with send status
- [ ] Compose announcement: write draft, select recipients (all / by ISO plan), schedule
- [ ] Admin → AI Config: edit `welcome_*` / `announcement_*` prompts in `ai_prompts` table (same UI as existing prompts)

### Frontend — Customer Workspace
- [ ] Tasks tab: notification tasks visible in history (non-interactive, read-only, distinct style)

---

## Phase 2 — ISO360 Service Flag + Annual Reminder
**Status: 🔲 Not started**

### DB Changes
- [ ] Migration `022`: Add `iso360_enabled`, `iso360_activated_at`, `iso360_annual_month`, `iso360_annual_day` to `customer_iso_plans`
- [ ] Migration `022`: Add `required_documents JSONB` to `iso_standards` (define per-standard document list)

### Backend
- [ ] ISO plan API: support `iso360_enabled` toggle (PUT `/api/v1/customers/{id}/plans/{plan_id}`)
- [ ] On ISO360 enable: auto-create ISO360 onboarding tasks (`source='iso360_onboarding'`, `requires_followup=FALSE`)

### Automation Service / Scheduler
- [ ] New scheduler job: daily check for plans where annual reminder is due
- [ ] Annual job: auto-create evidence tasks (`type='iso360_annual'`, `source_year=year`, `requires_followup=FALSE`)
- [ ] Annual job: insert `type='notification'` task — LLM generates reminder email body
- [ ] Escalation job: after 14 days flip unresolved `iso360_annual` tasks to `requires_followup=TRUE`

### Frontend — Admin
- [ ] ISO plan card: ISO360 toggle (enable/disable)
- [ ] ISO360 settings: configure reminder month/day
- [ ] Manual trigger: "Send Annual Reminder Now"

### Frontend — Customer Portal
- [ ] Tasks tab: "Annual Review" section for `source='iso360_annual'` tasks
- [ ] ISO360 badge in portal header when plan has ISO360 active

---

## Phase 3 — ISO Document Generation
**Status: 🔲 Not started**

### DB Changes
- [ ] Populate `iso_standards.required_documents` JSONB for each standard (27001, 27017, 9001...)
- [ ] Migration: add `iso360_doc_status JSONB` to `customer_iso_plans` (track generation state per doc type)

### AI Service
- [ ] New agent: `iso360_document_agent.py` — generates a single document type given customer data + ISO metadata
- [ ] Document generation queue: triggered when ISO360 onboarding tasks reach 70% completion
- [ ] Re-generation trigger: when collection answers reach 80% completion
- [ ] Store generated docs in customer storage + link in `documents` table

### Frontend — Admin
- [ ] ISO360 panel: document generation status per document type
- [ ] Manual trigger: "Regenerate All Documents" / per-document regenerate

### Frontend — Customer Portal
- [ ] New "Documents" tab: list generated documents with download links + generation date

---

## Phase 4 — Risk Assessment + Readiness Score + Audit Pack
**Status: 🔲 Not started**

### AI Service
- [ ] `risk_assessment_agent.py` — generates tailored risk assessment from customer answers + ISO risk domains + gaps
- [ ] Readiness score calculator — percentage from completed tasks vs total, with top blockers
- [ ] Audit pack generator — ZIP of all evidence files + documents organised by ISO clause

### Frontend — Admin
- [ ] Readiness score on customer workspace header
- [ ] Manual trigger: "Generate Risk Assessment"

### Frontend — Customer Portal
- [ ] Risk Assessment view (download PDF)
- [ ] Readiness Score widget in portal header with top 3 blockers
- [ ] Audit Pack button ("Download Audit Pack")

---

## Phase 5 — Supplier Assessment
**Status: 🔲 Not started**

### DB Changes
- [ ] Migration: create `customer_suppliers` table

### Backend
- [ ] CRUD endpoints for `customer_suppliers`
- [ ] Supplier questionnaire generation (LLM per supplier type + ISO controls)
- [ ] Send questionnaire via notification task to supplier contact email

### Frontend — Customer Portal
- [ ] New "Suppliers" tab (ISO360 only): add/edit suppliers, view assessment status
- [ ] Supplier risk dashboard: criticality × status grid

---

## Phase 6 — Proactive AI + Compliance Calendar
**Status: 🔲 Not started**

- [ ] Proactive compliance advisor: portal chat detects stale documents / changed answers → surfaces alerts
- [ ] Change impact analysis: when answer updated, flag affected documents for review
- [ ] Compliance calendar: upcoming obligations with deadlines, linked to tasks

---

## Progress Log

| Date | Phase | What was done |
|---|---|---|
| 2026-03-10 | Setup | Branch created, DB dumped, plan finalised |
