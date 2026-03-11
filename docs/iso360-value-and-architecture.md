# ISO360 — Value, Architecture & Roadmap

## What ISO360 Is

ISO360 transforms compliance from a one-time delivery into a year-round managed service.
Without it, a customer receives their ISO documents once and is left to figure out what to do next.
With ISO360, the platform owns their compliance calendar — scheduled tasks, evidence collection, reminders, and an audit trail — continuously, for the life of their subscription.

**The pitch:** *"We don't just get you certified — we keep you certified."*

---

## The Two-Layer Template System

### Layer 1 — Platform Templates (built once per ISO standard)

When an ISO standard is built with AI, the LLM reads the full PDF and outputs `recurring_activities[]` per template — real clause references, types, and frequencies. A second LLM pass then generates a structured template for each activity.

Each platform template contains:

| Field | Example |
|---|---|
| `title` | "Conduct Quarterly Access Rights Review" |
| `type` | `review` / `operational_activity` / `record` |
| `update_frequency` | `monthly` / `quarterly` / `yearly` / `event_based` |
| `responsible_role` | "Information Security Manager" |
| `steps` | 5–6 concrete, auditor-ready steps |
| `evidence_fields` | 6–15 fields an ISO auditor expects as proof |
| `iso_clause` | "5.18" |

ISO 27001:2022 produces 34 platform templates covering the full compliance lifecycle.
These are generic, reusable across all customers, and stored in `iso360_templates`.

### Layer 2 — Customer-Personalized Copy (built once per customer)

When a customer activates ISO360 and their onboarding reaches the configured threshold,
the `iso360_adjustment` LLM call personalizes the platform template for that specific organisation:

- Generic terms ("your CRM", "all systems") replaced with actual tools from their onboarding answers
- `responsible_role` adjusted to match their org structure
- Steps simplified for small companies (<10 people)

The personalized copy is stored in `customer_documents`, one per customer plan.

---

## How It Helps a Customer Through the Year

```
Platform templates (34 for ISO 27001:2022)
        ↓  iso360_adjustment LLM (per customer, at onboarding threshold)
Customer-personalized copy → customer_documents
        ↓  scheduler (monthly / quarterly / yearly cadence)
Tasks created → customer_tasks
        ↓  automation-service
Email reminders sent → customer portal
        ↓  customer
Fills evidence fields, uploads proof files
        ↓  system
Completion tracked: last_completed_at, next_due_date updated
        ↓  admin dashboard
ISO360 health visible per customer (X of Y activities completed)
```

**Example calendar for an ISO 27001:2022 customer:**

| When | Task |
|---|---|
| Every month | Review security logs and monitoring alerts (5 steps, 6 evidence fields) |
| Every quarter | Conduct Access Rights Review — fill 6 fields, upload approval record |
| Every year (January) | Conduct Annual ISMS Management Review |
| Every year (March) | Execute Internal Audit Programme |
| On incident | "Respond to Information Security Incident" task auto-created |
| On new hire | "Conduct candidate background verification" task auto-created |

---

## Why It's a Premium Service

| Without ISO360 | With ISO360 |
|---|---|
| Customer gets documents once | Year-round compliance calendar |
| They figure out what to do next | Tasks appear automatically, on schedule |
| Audit prep = panic | Evidence collected continuously |
| You deliver once, revenue stops | Recurring subscription justification |
| Customer drifts out of compliance | Platform keeps them in compliance |

ISO360 is the mechanism that converts a one-time project fee into an ongoing subscription.
Every month the scheduler runs, every reminder sent, every evidence field filled — that is the service being delivered.

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1 — ISO Build  (ai-service, OpenAI)                  │
│  ISO PDF → recurring_activities[] per template              │
│  Stored: templates.recurring_activities                     │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 2 — Platform Template Generation  (automation-svc)   │
│  Each activity → LLM → title, role, steps, evidence fields  │
│  Stored: iso360_templates + iso360_template_iso_mapping     │
└─────────────────────────────────────────────────────────────┘
                        ↓  (on customer ISO360 activation)
┌─────────────────────────────────────────────────────────────┐
│  Phase 3 — Customer Adjustment  (automation-svc)            │
│  Platform template + customer onboarding answers → LLM      │
│  → personalized steps referencing their actual tools        │
│  Stored: customer_documents                                 │
└─────────────────────────────────────────────────────────────┘
                        ↓  (scheduler: monthly / quarterly / yearly)
┌─────────────────────────────────────────────────────────────┐
│  Phase 4 — Task Delivery  (scheduler + automation-svc)      │
│  customer_tasks created from due templates                  │
│  Email reminders → customer portal → evidence upload        │
│  Completion: last_completed_at, next_due_date updated       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 5 — Admin Visibility  (dashboard)                    │
│  Per-customer ISO360 health (X/Y activities completed)      │
│  Overdue alerts, audit export                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Database Tables

| Table | Purpose |
|---|---|
| `templates.recurring_activities` | LLM-extracted activities per ISO template (from build) |
| `iso_standards.iso360_recurring_activities` | Cross-cutting activities (management review, audit) |
| `iso360_templates` | Platform-level templates (shared across all customers) |
| `iso360_template_iso_mapping` | Links templates to ISO standards they cover |
| `iso360_plan_settings` | Per-customer config: reminder day, onboarding threshold |
| `customer_documents` | Personalized template copy per customer plan |
| `customer_tasks` | Scheduled compliance tasks per customer |

---

## Implementation Status

| Phase | Status | Notes |
|---|---|---|
| ISO Build → recurring_activities | ✅ Done | Migration 024, stream_consumer.py |
| Platform template generation | ✅ Done | 34 templates for ISO 27001:2022, OpenAI |
| Customer adjustment (LLM personalization) | 🔲 Next | iso360_adjustment prompt ready, needs trigger logic |
| Scheduler task creation | 🔲 Next | `_iso360_annual_job` skeleton exists |
| Customer portal task display | 🔲 Next | Extend TaskDetailModal with evidence fields |
| Evidence collection & completion tracking | 🔲 Next | last_completed_at, next_due_date updates |
| Admin ISO360 health dashboard | 🔲 Backlog | Per-customer completion visibility |

---

## Future: Move Template Generation to ai-service

Currently Phase 2 (platform template generation) runs inline inside automation-service.
The right long-term home is ai-service, which already provides:
- Semaphore-controlled rate limiting across all LLM calls
- 3-retry with exponential backoff (no fallback stubs)
- Token and cost telemetry per template
- Unified provider routing (OpenAI / Gemini / Anthropic / Groq)

Estimated effort: ~2 hours. Candidate for after Phase 3 (customer adjustment) is stable.
