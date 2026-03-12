# ISO360 — Full Implementation Plan

## Current Status (Done ✅)

| Phase | What | Status |
|---|---|---|
| 1 | ISO build outputs recurring_activities[] per template | ✅ Done |
| 2 | Platform template generation (34 templates, ai-service→automation) | ✅ Done |
| 3 | Customer adjustment — personalize templates per customer context | ✅ Done |
| UI | ISO360 tab in customer workspace (activities list + detail modal) | ✅ Done |

---

## Upcoming Work

---

## AI Architecture Migration
**Goal:** Batch/heavy LLM jobs move to ai-service. Email-related AI helpers stay in automation-service.

### Decision rule

| Type | Home | Reason |
|---|---|---|
| Bulk/batch LLM jobs (34+ calls, no real-time dependency) | ai-service | Needs retry, rate limiting, usage tracking |
| Lightweight inline LLM helpers tightly coupled to email flow | automation-service | Moving adds latency/complexity for no gain |

### What moves — ISO360 batch agents only

| Agent | Currently | Moves to |
|---|---|---|
| `iso360_template_agent` | automation-service | ai-service |
| `iso360_adjustment_agent` | automation-service | ai-service |

### What stays in automation-service

| Agent | Reason |
|---|---|
| `notification_email_agent` | Inline email HTML generation — glued to SMTP send flow |
| `email_extract_agent` | Inline extraction — glued to IMAP receive flow |

### New Redis streams in ai-service

```
ai:iso360_template     → generate platform templates (replaces automation:iso360_template)
ai:iso360_adjustment   → personalize per customer   (replaces automation:iso360_adjustment)
ai:iso360_kyc          → generate KYC questions     (new — Phase 5a)
```

### What automation-service keeps
- Email sending (SMTP/SendGrid) + email content generation (inline)
- Email extraction (inline, part of IMAP flow)
- Scheduler (APScheduler jobs)
- Stream orchestration — pushes ISO360 jobs to ai-service, polls result key
- Task creation in DB

### Migration steps
1. Move `iso360_template_agent.py` and `iso360_adjustment_agent.py` to `ai-service/agents/`
2. Add stream handlers in `ai-service/stream_consumer.py` for the two new streams
3. Update automation-service to push to `ai:iso360_template` / `ai:iso360_adjustment` and poll result key
4. Remove `openai` from automation-service direct agent calls (keep for email agents)
5. Rebuild both containers

---

## Phase 4 — Task Delivery
**Goal:** Scheduled and event-based activities reach the customer as tasks.

### 4a — Scheduler: calendar activities

Daily job in automation-service:
```
Find customer_documents WHERE:
  document_type = 'iso360_activity'
  AND next_due_date <= TODAY + 7 days
  AND last_completed_at IS NULL
  AND excluded = FALSE
  AND no open customer_task already exists for this doc
→ Create customer_task (type='iso360_activity', source='iso360_scheduled')
→ Send notification email
→ Task appears in customer portal Tasks tab with purple ISO360 badge
```

On task completion:
```
customer marks task done + uploads evidence
→ last_completed_at = NOW()
→ next_due_date advances (+ 1 month/quarter/year)
→ task closed
```

### 4b — Manual trigger for event-based

In ISO360 tab, each event-based activity gets a "Trigger" button.
Admin clicks → creates customer_task immediately → customer notified.

### 4c — Activity exclude toggle

Add `excluded BOOLEAN DEFAULT FALSE` to `customer_documents`.
ISO360 tab: toggle switch per activity row.
Excluded activities never generate tasks and are visually dimmed.

### 4d — Tasks tab: ISO360 filter

Existing tasks tab gets an "ISO360" filter pill.
ISO360 tasks show a purple Shield badge, link back to activity detail.

### 4e — TaskDetailModal: ISO360 activity view

When a task has `source='iso360_activity'`, the detail modal shows:
- The numbered steps (from the personalized template)
- Evidence fields with upload capability
- ISO clause reference
- "Mark Complete" button (requires at least one evidence field filled)

### DB changes needed
```sql
ALTER TABLE dna_app.customer_documents ADD COLUMN excluded BOOLEAN DEFAULT FALSE;
-- (no new tables needed — customer_tasks table already handles ISO360 tasks)
```

---

## Phase 5 — KYC + Admin Health Dashboard

### 5a — ISO360 KYC Step
**Goal:** Before customer adjustment, AI generates ISO-specific questions to improve personalization quality.

**Flow:**
```
Threshold met (70%)
  ↓
ai-service: review existing answers → generate 10 KYC questions
  (e.g. "What ticketing system do you use for access requests?",
        "Do you have a SIEM? Which one?",
        "Do you have a formal incident response team?")
  ↓
Special task type='iso360_kyc' created → customer sees guided form in portal
  ↓
Customer answers (2-3 day window, escalation reminder after 48h)
  ↓
Adjustment job runs with KYC answers + existing Q&A → rich personalization
  (steps reference actual tools: "Create a ticket in Jira SECURITY board"
   instead of "use your project management tool")
```

**DB:** New table `iso360_kyc_answers (plan_id, question, answer, answered_at)`

**New Redis stream:** `ai:iso360_kyc`

**New ai_prompts:**
- `iso360_kyc_system` — generate targeted compliance questions
- `iso360_kyc_user` — takes existing answers + ISO standard context

### 5b — Admin ISO360 Health Dashboard

New section in Admin → ISO Studio or in the customer list view:

```
┌──────────────────────────────────────────────────────────────────┐
│ ISO360 Health — All Customers          March 2026                │
├──────────┬──────────────┬──────────┬───────────┬────────────────┤
│ Customer │ Standard     │ On Track │ Overdue   │ Last Activity  │
├──────────┼──────────────┼──────────┼───────────┼────────────────┤
│ Avi      │ ISO 27001    │ 31/33    │ 2         │ Mar 11, 2026   │
│ Acme     │ ISO 27001    │ 28/33    │ 5 ⚠️      │ Feb 28, 2026   │
└──────────┴──────────────┴──────────┴───────────┴────────────────┘
```

Also: per-customer ISO360 progress ring on the customer list card.

### 5c — Customer Portal: ISO360 View

Dedicated section in customer portal (not just tasks):
- Compliance calendar (month view, activities due this month)
- Activity history (completed with evidence)
- "My ISO360 Score" — % of scheduled activities completed on time this year

---

## Build Order

```
1. AI Architecture Migration     ← clean the foundation first
2. Phase 4a (calendar tasks)     ← core value delivery
3. Phase 4b (event trigger btn)  ← event-based
4. Phase 4c (exclude toggle)     ← admin control
5. Phase 4d+e (tasks tab + modal)← customer UX
6. Phase 5a (KYC)                ← quality improvement
7. Phase 5b (health dashboard)   ← admin visibility
8. Phase 5c (portal view)        ← customer premium experience
```

---

## Summary Table

| # | What | Effort | Value |
|---|---|---|---|
| AI Migration | Move 4 agents to ai-service | Medium | High (architecture) |
| Phase 4a | Scheduler creates tasks from due docs | Medium | Critical |
| Phase 4b | Trigger button for event-based | Small | High |
| Phase 4c | Exclude toggle per activity | Small | Medium |
| Phase 4d+e | Tasks tab filter + ISO360 modal | Medium | High |
| Phase 5a | KYC questionnaire step | Large | High (quality) |
| Phase 5b | Admin health dashboard | Medium | High (visibility) |
| Phase 5c | Customer portal ISO360 view | Large | Very High (premium) |
