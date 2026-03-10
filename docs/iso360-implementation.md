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
- [ ] Migration `021`: Create `task_execution_log` table

### Backend
- [ ] `customer_tasks` task types extended: `'notification'` added as valid type
- [ ] Scheduler: filter `requires_followup = TRUE` on all follow-up queries
- [ ] `iso_customers.py`: on customer create → insert `type='notification'` task (welcome_customer)
- [ ] `iso_customers.py`: on plan activate → insert `type='notification'` task (welcome_plan)
- [ ] New route: `POST /api/v1/notifications/broadcast` — admin creates announcement for all/filtered customers

### Automation Service
- [ ] `stream_consumer.py` or new handler: process `type='notification'` pending tasks
- [ ] LLM-generate `welcome_plan` body (ISO-specific, personalised)
- [ ] Static template for `welcome_customer` (no plan context yet)
- [ ] On send: update task `status='completed'`, insert `task_execution_log` row
- [ ] On failure: update `last_error`, increment `retry_count`, insert `task_execution_log` row
- [ ] Retry logic: re-attempt failed notification tasks up to 3 times

### Frontend — Admin
- [ ] Admin → Automation: new "Outbound" tab showing `type='notification'` tasks with status
- [ ] Compose announcement: write subject/body, select recipients (all / by ISO plan), schedule

### Frontend — Customer Workspace
- [ ] Tasks tab: show notification tasks in history (non-interactive, read-only)

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
