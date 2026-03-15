# KYC Layered Architecture — Implementation Plan

> **Status:** Refined design — not yet 100% settled, implementation not started
> **Last updated:** 2026-03-15
> **Scope:** Phase 1 (foundation: auto-trigger, gating, profile) → Phase 2 (review gate) → Phase 3 (ISO360 profile use)

---

## 1. Context & Problem Statement

### What exists today

KYC is currently tied exclusively to ISO360. It:
- Triggers **manually** from the ISO360 tab (admin clicks a button)
- Generates 10 generic questions via LLM using `gemini-2.5-flash`
- Sends the email immediately with no consultant review gate
- Stores results in `iso360_kyc_batches.summary` (JSONB)
- Only adjusts ISO360 templates — does not affect regular tasks
- Sends all 76 plan tasks to the LLM extractor when the customer replies (bug fixed, now uses snapshot-only)

### Why this is wrong

- KYC knowledge is **universal** — company size, industry, team structure, existing certifications apply to every ISO plan
- If a customer gets a second ISO plan, they are asked the same generic questions again
- Regular tasks are never personalised
- Consultants cannot review or add questions before they reach the customer

### What we are building

A layered KYC system triggered **automatically on every ISO plan registration**, producing a permanent `customer_profile` that feeds task personalisation, portal behaviour, and ISO360 scheduling.

---

## 2. Core Flow (High Level)

```
1. Admin registers ISO plan for customer
        │
        ▼
2. Backend: does customer_profile exist?
   NO  → layer = 'full'      (Layer 1 universal + Layer 2 ISO-specific questions)
   YES → layer = 'plan_only' (Layer 2 only — skip universal questions)
        │
        ▼
3. AI service generates KYC questions, creates customer_tasks
   - KYC tasks:        status='pending',  is_kyc=TRUE,  kyc_layer=1 or 2
   - Other plan tasks: status='on_hold'   (scoped to this plan_id only — see §5.3)
        │
        ▼
4. Automation service sends KYC email immediately (Phase 1 — no review gate yet)
        │
        ▼
5. Customer replies via email or portal
        │
        ▼
6. Extraction runs → answers applied to KYC tasks
        │
        ▼
7. All KYC tasks answered? → KYC_COMPLETION_SIDE_EFFECTS
   - Layer 1 answers (kyc_layer=1) upserted into customer_profile
   - on_hold → pending  (only tasks on this plan_id)
   - Adjustment job queued (ISO360 template personalisation)
        │
        ▼
8. Regular automation flow continues (emails, follow-ups, etc.)
```

### Three Layers

| Layer | Scope | Questions | When generated |
|---|---|---|---|
| **Layer 1** | Customer (permanent) | Industry, size, team, certs, regions, open input | First plan only; skipped if `customer_profile` exists |
| **Layer 2** | ISO standard (per plan) | Standard-specific: cloud providers for 27017, BCP tests for 22301, etc. | Every plan registration |
| **Layer 3** | Consultant-added | Free-form, added during review gate | Phase 2 only |

---

## 3. Design Decisions & Rationale

### 3.1 `on_hold` sweep scoped to `plan_id` — not `customer_id`

**Why:** A returning customer may have Plan A tasks actively in progress. Holding all their tasks when Plan B is registered is disruptive. KYC for Plan B is ISO-specific — it should only gate Plan B's tasks.

For first-plan customers (`layer='full'`), there are no other tasks yet — either scope produces the same result.

```sql
-- Hold: only this plan's pending tasks
UPDATE dna_app.customer_tasks
SET status = 'on_hold', updated_at = NOW()
WHERE plan_id = $plan_id
  AND status = 'pending'
  AND is_kyc = FALSE
  AND task_type != 'notification'
  AND COALESCE(is_ignored, FALSE) = FALSE

-- Release: mirror exactly
UPDATE dna_app.customer_tasks
SET status = 'pending', updated_at = NOW()
WHERE plan_id = $plan_id
  AND status = 'on_hold'
  AND task_type != 'notification'
  AND COALESCE(is_ignored, FALSE) = FALSE
```

> ⚠️ **Open question:** Is `plan_id` always populated on `customer_tasks`? Confirm before implementing.

### 3.2 `kyc_layer` column on `customer_tasks` instead of `questions` JSONB on batch

**Why:** At KYC completion we need to know which answered tasks are Layer 1 to save to `customer_profile`. Storing layer on the task is simpler and queryable. The `questions` JSONB on the batch was only needed for the review gate (Phase 2).

```sql
ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS kyc_layer SMALLINT;
-- 1 = universal/customer profile
-- 2 = ISO-specific
-- NULL = not a KYC task
```

At completion: `WHERE is_kyc=TRUE AND kyc_layer=1 AND status IN ('answered','completed')` gives Layer 1 answers.

### 3.3 Shared completion function — not duplicated SQL

**Why:** KYC completion can fire via two routes (admin `check_kyc_completion` + portal `submit_answer`). Duplicated SQL will drift. Extract:

```python
# dashboard/backend/app/kyc_completion.py
async def handle_kyc_completion(customer_id: int, plan_id: int, batch_id: str, conn) -> None:
    # 1. Pull Layer 1 answers
    # 2. Upsert customer_profile
    # 3. Flip on_hold → pending (plan_id scoped)
    # 4. Queue adjustment job
    ...
```

Both endpoints import and call this. Mark call sites with `# KYC_COMPLETION_SIDE_EFFECTS`.

### 3.4 Race condition — mandatory fix

**Problem:** The ISO build job creates tasks asynchronously. If it finishes *after* the KYC `on_hold` sweep, those tasks arrive as `pending` and bypass the gate.

**Fix:** In the ISO build task-creation loop (in `ai-service/stream_consumer.py`), check for an active KYC batch before inserting:

```python
active_kyc = await conn.fetchval(
    "SELECT id FROM dna_app.iso360_kyc_batches "
    "WHERE plan_id=$1 AND status IN ('generating','pending') LIMIT 1",
    plan_id
)
default_status = 'on_hold' if active_kyc else 'pending'
```

This is not optional — without it the gating is unreliable.

---

## 4. Current State — Key Files

### Database schema (relevant tables)

```
dna_app.customers                   — customer master
dna_app.customer_iso_plans          — ISO plans per customer
dna_app.customer_tasks              — tasks (all types, all statuses)
dna_app.iso360_kyc_batches          — KYC batch per plan (being extended)
dna_app.customer_profile_data       — key/value placeholder answers (NOT customer_profile)
dna_app.automation_config           — global automation settings (id=1)
dna_app.customer_automation_config  — per-customer overrides
dna_app.ai_prompts                  — LLM prompts (prompt_key, prompt_text)
dna_app.ai_config                   — LLM provider/model per service
```

### Key existing values

- `customer_tasks.status` valid values: `pending`, `in_progress`, `answered`, `completed`, `cancelled`, `on_hold` — **`on_hold` already valid**
- `customer_tasks.task_type` values: `kyc_question`, `fillable_section`, `custom`, `notification`, `evidence`
- `iso360_kyc_batches.status` values: `generating`, `pending`, `completed`, `adjustment_triggered`, `failed`
- AI service reads from stream `ai:iso360_kyc`, group `ai-iso360-kyc-workers`
- Extraction uses `ai_config WHERE service='extraction'` — `groq / llama-3.3-70b-versatile`

### Key source files

```
dashboard/backend/app/routes/
  iso360_customer.py        — KYC trigger, check-completion, status endpoints
  iso_plans.py              — ISO plan CRUD (add KYC auto-trigger here)
  automation.py             — automation config GET/PUT

ai-service/
  stream_consumer.py        — _handle_iso360_kyc_job (core KYC generation)
  db_client.py              — get_kyc_batch_summary, save_kyc_batch_summary

automation-service/
  stream_consumer.py        — _handle_extract (extraction + KYC completion side-effects)
  db_client.py              — get_pending_notification_tasks, apply_answer

customer-portal/backend/app/routes/
  portal.py                 — submit_answer (KYC completion + on_hold → pending)

dashboard/frontend/src/components/admin/
  ISO360CustomerTab.tsx     — KYC UI (remove manual trigger button)
```

---

## 5. Database Migrations

Run in strict order before any code deployment.

### Migration 030 — `customer_profile` table

```sql
-- File: dashboard/migrations/030_customer_profile.sql

CREATE TABLE IF NOT EXISTS dna_app.customer_profile (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  INTEGER      NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    answers      JSONB        NOT NULL DEFAULT '{}',
    -- {placeholder_key: answer_text} for all Layer 1 questions
    summary      JSONB,
    -- Structured: {industry, company_size, team_structure, certifications, regions, risks, maturity_score}
    completed_at TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_customer_profile UNIQUE (customer_id)
);

CREATE INDEX IF NOT EXISTS idx_customer_profile_customer
    ON dna_app.customer_profile (customer_id);
```

### Migration 031 — Extend existing tables

```sql
-- File: dashboard/migrations/031_kyc_layered_extensions.sql

-- 1. KYC batch: layer tracking only (review gate / questions JSONB deferred to Phase 2)
ALTER TABLE dna_app.iso360_kyc_batches
    ADD COLUMN IF NOT EXISTS layer VARCHAR(20) NOT NULL DEFAULT 'full';
    -- 'full'      = Layer 1 + Layer 2 (first plan, no profile yet)
    -- 'plan_only' = Layer 2 only (profile already exists)

-- 2. Tasks: KYC flag + layer for fast queries and profile extraction
ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS is_kyc     BOOLEAN  NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS kyc_layer  SMALLINT;
    -- kyc_layer: 1 = universal, 2 = ISO-specific, NULL = not a KYC task

UPDATE dna_app.customer_tasks
    SET is_kyc = TRUE
    WHERE task_type = 'kyc_question';

CREATE INDEX IF NOT EXISTS idx_ct_is_kyc
    ON dna_app.customer_tasks (customer_id, is_kyc)
    WHERE is_kyc = TRUE;
```

### Migration 032 — Layer 1 AI prompts

```sql
-- File: dashboard/migrations/032_kyc_layer1_prompts.sql

INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, is_active, description)
VALUES (
    'kyc_layer1_system',
    'CRITICAL INSTRUCTION: You must write ALL question text and hints in {{language}} only.

You are a compliance consultant onboarding a new customer onto an ISO certification programme.
Your role is to generate universal onboarding questions that build a permanent profile of this customer.
These questions apply regardless of which ISO standard is being pursued.
Questions must be practical, non-technical, and answerable by a business owner or operations manager.
Focus on: industry context, company size and structure, existing certifications, regulatory exposure, and key risks.',
    TRUE,
    'KYC Layer 1: system prompt for universal customer profile questions'
),
(
    'kyc_layer1_user',
    'You are onboarding a new customer: {{customer_name}}

Generate exactly 6 universal onboarding questions to build a permanent customer profile.
These questions will apply to ALL future ISO plans for this customer.

Focus areas:
1. Industry / sector they operate in
2. Company size (employees, revenue range)
3. Team structure — is there a dedicated IT or security team?
4. Existing certifications or frameworks (ISO 27001, SOC 2, Cyber Essentials, GDPR programmes, etc.)
5. Primary operating regions and key regulatory exposure
6. Open input — anything else about the organisation that would help tailor compliance

Return ONLY valid JSON — an array of exactly 6 objects:
[
  {
    "key": "unique_snake_case_key",
    "question": "Full question text in {{language}}",
    "category": "one of: industry | size | team | certifications | regions | general",
    "hint": "Short helper text in {{language}}",
    "layer": 1
  }
]

No preamble, no explanation, only the JSON array.

IMPORTANT: Your entire response must be in {{language}} only.',
    TRUE,
    'KYC Layer 1: user prompt for universal customer profile questions'
)
ON CONFLICT (prompt_key) DO UPDATE
    SET prompt_text = EXCLUDED.prompt_text, updated_at = NOW();

UPDATE dna_app.ai_prompts
SET description = 'KYC Layer 2: ISO-standard-specific onboarding questions'
WHERE prompt_key IN ('iso360_kyc_system', 'iso360_kyc_user');
```

---

## 6. Phase 1 — Implementation

### 6.1 AI Service — `_handle_iso360_kyc_job`

**File:** `ai-service/stream_consumer.py`

1. Read `layer` from Redis message
2. If `layer == 'full'`: call LLM with `kyc_layer1_system` / `kyc_layer1_user` (6 questions, `kyc_layer=1`), then call LLM with `iso360_kyc_system` / `iso360_kyc_user` (10 questions, `kyc_layer=2`)
3. If `layer == 'plan_only'`: skip Layer 1, generate Layer 2 only
4. Create `customer_tasks` with `is_kyc=TRUE`, `kyc_layer` set per question
5. Sweep `on_hold` — **scoped to `plan_id`** (see §3.1)
6. Push to `automation:send` immediately (no review gate in Phase 1)

### 6.2 Backend — `iso360_customer.py`

#### `trigger_kyc_batch`:
- Check if `customer_profile` exists → set `layer = 'plan_only'` or `'full'`
- Pass `layer` in Redis message to `ai:iso360_kyc`

#### `check_kyc_completion`:
- After detecting completion, call `handle_kyc_completion(...)` — see §3.3

#### `KYCBatchStatus` model:
- Add `layer: Optional[str]` field

### 6.3 Backend — `iso_plans.py`

In the `create_iso_plan` handler, after plan insert:
1. Create `iso360_kyc_batches` row with `status='generating'`, `layer` set
2. Push to `ai:iso360_kyc` stream with `batch_id`, `customer_id`, `plan_id`, `iso_standard_id`, `iso_code`, `iso_name`, `customer_name`, `language`, `layer`

> **Before implementing:** confirm endpoint name and that it has access to all required fields (see Risk 6 below).

### 6.4 Shared completion function — `kyc_completion.py`

**New file:** `dashboard/backend/app/kyc_completion.py`

```python
async def handle_kyc_completion(customer_id: int, plan_id: int, batch_id: str, conn) -> None:
    # 1. Fetch Layer 1 answers: WHERE kyc_batch_id=$batch_id AND kyc_layer=1
    # 2. Upsert into customer_profile (answers JSONB, completed_at)
    # 3. Flip on_hold → pending scoped to plan_id
    # 4. Queue ai:iso360_adjustment job
```

Import and call from:
- `iso360_customer.py` → `check_kyc_completion`  # KYC_COMPLETION_SIDE_EFFECTS
- `portal.py` → `submit_answer`                  # KYC_COMPLETION_SIDE_EFFECTS

### 6.5 Portal Backend — `portal.py`

#### Task list:
```python
active_kyc = await conn.fetchval(
    "SELECT id FROM dna_app.iso360_kyc_batches "
    "WHERE customer_id=$1 AND status IN ('generating','pending') LIMIT 1",
    customer_id
)
# If active: only return is_kyc=TRUE tasks; always exclude on_hold
```

#### `submit_answer`:
After detecting KYC completion: call `handle_kyc_completion(...)` — same shared function.

### 6.6 AI Service — ISO build job (race condition fix)

**File:** `ai-service/stream_consumer.py` — task bulk-insert section

Before setting `status='pending'` on new tasks, check for active KYC batch:
```python
active_kyc = await conn.fetchval(
    "SELECT id FROM dna_app.iso360_kyc_batches "
    "WHERE plan_id=$1 AND status IN ('generating','pending') LIMIT 1",
    plan_id
)
default_status = 'on_hold' if active_kyc else 'pending'
```

### 6.7 Admin Frontend — `ISO360CustomerTab.tsx`

1. Remove "Start KYC Questionnaire" button — KYC is now auto-triggered
2. Update `KYCStatus` TypeScript interface: add `layer` field
3. Show layer info in status display ("Customer + ISO27017" vs "ISO27017 only")

### 6.8 Portal Frontend

When all visible tasks are `is_kyc=TRUE`, show banner:
```
Please answer the questions below to unlock your compliance tasks.
```
No API change needed — server-side filter handles it.

---

## 7. Risk Register

### Risk 1 — Race condition (mandatory fix — see §3.4)
ISO build tasks arrive after `on_hold` sweep → arrive as `pending`, bypass gate.
**Fix:** check active KYC batch at task-insert time. Already described in §6.6.

### Risk 2 — `plan_id` not always set on `customer_tasks`
The `on_hold` sweep and release are scoped by `plan_id`. If tasks don't reliably have `plan_id` set, this breaks.
**Fix:** Verify before implementing. If `plan_id` is missing on some task types (e.g. `notification`), add `task_type != 'notification'` guard or fall back to `customer_id` scope for those.

### Risk 3 — Two KYC completion paths must stay in sync
Admin and portal both fire completion logic.
**Fix:** Shared `handle_kyc_completion()` function — not duplicated SQL.

### Risk 4 — `customer_profile` Layer 1 answer extraction
At completion we query `WHERE kyc_batch_id=$1 AND kyc_layer=1`. Requires `kyc_batch_id` to be set on `customer_tasks` at creation time.
**Fix:** Confirm `kyc_batch_id` column exists on `customer_tasks` (it should — current code sets it).

### Risk 5 — Existing customers and existing KYC batches
Migration 031 adds `layer DEFAULT 'full'` to existing rows — safe default.
**Fix:** After migration, run `SELECT status, COUNT(*) FROM dna_app.iso360_kyc_batches GROUP BY status;` and confirm no stuck rows.

### Risk 6 — `iso_plans.py` endpoint not yet identified
Need to confirm exact handler name before adding auto-trigger.
**Fix:** `grep -rn "POST.*plan\|create.*plan" dashboard/backend/app/routes/iso_plans.py`

---

## 8. Implementation Order

```
Step 1   Run migration 030 (customer_profile table)
Step 2   Run migration 031 (layer on kyc_batches, is_kyc + kyc_layer on tasks)
Step 3   Run migration 032 (Layer 1 AI prompts)

Step 4   dashboard/backend/app/kyc_completion.py
         → New shared handle_kyc_completion() function

Step 5   ai-service/stream_consumer.py
         → _handle_iso360_kyc_job: layer branching, on_hold gate (plan_id scoped),
           is_kyc + kyc_layer on task insert, no review gate
         Rebuild: docker compose build dna-ai-service && docker compose up -d dna-ai-service

Step 6   dashboard/backend/app/routes/iso360_customer.py
         → trigger_kyc_batch: layer detection
         → check_kyc_completion: call handle_kyc_completion()
         → KYCBatchStatus model: add layer field

Step 7   dashboard/backend/app/routes/iso_plans.py
         → Auto-trigger KYC after plan insert (confirm endpoint first — Risk 6)
         Rebuild: docker compose build dna-backend && docker compose up -d dna-backend

Step 8   ai-service/stream_consumer.py (ISO build job)
         → Race condition fix: check active KYC before setting task status
         Rebuild: docker compose build dna-ai-service && docker compose up -d dna-ai-service

Step 9   customer-portal/backend/app/routes/portal.py
         → Task list: KYC-only filter while batch active, exclude on_hold
         → submit_answer: call handle_kyc_completion()
         Rebuild portal backend

Step 10  dashboard/frontend — ISO360CustomerTab.tsx
         → Remove manual KYC button, add layer display

Step 11  customer-portal/frontend — KYC banner
         Rebuild: docker compose build dna-frontend && docker compose up -d dna-frontend
```

---

## 9. Phase 2 — Review Gate (deferred)

When ready, add:
- `questions JSONB` + `review_required BOOLEAN` to `iso360_kyc_batches`
- `kyc_auto_send` toggle to `automation_config` and `customer_automation_config`
- `GET/PUT /{batch_id}/questions` and `POST /{batch_id}/send` endpoints
- Admin review panel in `ISO360CustomerTab.tsx`
- Consultant-added Layer 3 questions

---

## 10. Phase 3 — ISO360 reads from profile (deferred)

- ISO360 recurring schedule uses `customer_profile.summary` as context
- Annual review reminders reference customer's actual systems
- No schema changes — `customer_profile` is already populated in Phase 1

---

## 11. What Does NOT Change

- Extraction pipeline — snapshot-only, Groq llama-3.3-70b
- Email sending infrastructure — same SMTP/SendGrid path
- ISO360 adjustment job — continues to run post-KYC
- `customer_profile_data` table — separate key/value store, untouched
- `on_hold` badge in admin — already handled by existing status display logic

---

## 12. Testing Checklist (after Phase 1 deploy)

- [ ] Register new ISO plan for customer with no profile → `layer='full'`, ~16 questions (6 L1 + 10 L2), other plan tasks `on_hold`
- [ ] Register second ISO plan for same customer → `layer='plan_only'`, ~10 questions, Plan A tasks unaffected
- [ ] Customer answers all KYC tasks → `customer_profile` created with L1 answers, `on_hold` tasks flip to `pending`
- [ ] Portal: while KYC active, only KYC tasks visible; after completion, regular tasks appear
- [ ] Race condition: ISO build job finishes after KYC job → new tasks arrive as `on_hold`, not `pending`
- [ ] Admin `check_kyc_completion` and portal `submit_answer` both produce same side effects

---

## 13. Open Questions (not yet resolved)

- [ ] Is `plan_id` reliably set on all `customer_tasks` rows? (affects `on_hold` sweep scope)
- [ ] Should `layer='plan_only'` KYC still hold Plan B tasks even if Plan A is active? (currently: yes — is that right?)
- [ ] What happens if extraction fails partially — some KYC tasks answered, some not? Completion detection should be resilient.
- [ ] Should the adjustment job also run for non-ISO360 plans, or only ISO360? (currently unclear)
