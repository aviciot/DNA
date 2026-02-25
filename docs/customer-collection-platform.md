# DNA — Customer Data Collection Platform Design

## Overview

When a customer is assigned an ISO plan, DNA must collect all data needed to fill every `{{placeholder}}` across every template in that plan. The goal: collect each unique data point **exactly once**, regardless of how many documents use it, and propagate that answer to every current and future document automatically.

---

## 1. Data Model

### Existing Flow (What We Have)

```
iso_standards
  └── templates  (fixed_sections + fillable_sections with {{placeholders}})
        └── template_iso_mapping

customer_iso_plans  (customer enrolled in an ISO)
  └── customer_placeholders  (UNIQUE customer+plan+key — deduped)
        └── customer_profile_data  (ONE value per field_key per customer — shared across ALL plans)
              └── [DB trigger] → customer_documents  (auto-filled)
```

`customer_profile_data` is the **single source of truth**. Answer `{{organization_name}}` once — the trigger propagates it to every document across every plan. This is already correct architecture. We build on top of it.

---

## 2. Weak Spots & Fixes

| Weak Spot | Impact | Fix |
|---|---|---|
| `customer_placeholders` has no `question` or `category` | Can't show the right question without re-querying all templates | Add `question`, `category`, `hint`, `example_value` columns |
| Nothing seeds `customer_placeholders` on plan assignment | Plans exist but placeholder rows are never created | Build `seed_placeholders()` called on plan assignment |
| `customer_documents` not auto-created on plan assignment | Documents only exist if manually created | Auto-create one doc per template on assignment |
| `unique_active_iso_per_customer` constraint | Blocks same ISO in two languages for one customer | Drop or relax — use `(customer_id, iso_standard_id, language)` |
| No `collection_channels` table | No way to track how/where data was collected | Create table (see below) |
| `customer_profile_data` has no `display_label` | UI has no human-readable name for a raw `field_key` | Add `display_label varchar(500)` |
| No answer history / audit trail | Can't see who changed what and when | Add `customer_profile_data_history` table in Phase 2 |
| Confidence/source not surfaced in UI | Admin can't tell if a value was AI-guessed or human-confirmed | Surface `source` + `confidence` + `verified` in workspace UI |

---

## 3. Schema Additions

```sql
-- Richer placeholders
ALTER TABLE dna_app.customer_placeholders
    ADD COLUMN IF NOT EXISTS question      text,
    ADD COLUMN IF NOT EXISTS category      varchar(100) DEFAULT 'General',
    ADD COLUMN IF NOT EXISTS hint          text,
    ADD COLUMN IF NOT EXISTS example_value text;

-- Richer profile data
ALTER TABLE dna_app.customer_profile_data
    ADD COLUMN IF NOT EXISTS display_label varchar(500);

-- Collection channels
CREATE TABLE IF NOT EXISTS dna_app.collection_channels (
    id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_id      integer NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id          uuid REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    channel_type     varchar(50) NOT NULL,  -- 'manual'|'share_link'|'email'|'chat'|'folder'
    channel_config   jsonb DEFAULT '{}',    -- email addr, folder path, webhook URL, etc.
    share_token      varchar(100) UNIQUE,   -- tokenized public URL (no login)
    token_expires_at timestamptz,
    is_active        boolean DEFAULT true,
    created_by       integer REFERENCES auth.users(id),
    created_at       timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_collection_channels_customer
    ON dna_app.collection_channels(customer_id);
CREATE INDEX IF NOT EXISTS idx_collection_channels_token
    ON dna_app.collection_channels(share_token) WHERE share_token IS NOT NULL;
```

---

## 4. Plan Assignment Flow

When admin assigns an ISO plan to a customer:

```
1. INSERT customer_iso_plans

2. seed_placeholders(customer_id, plan_id, iso_standard_id)
   - Fetch all templates linked to ISO via template_iso_mapping
   - For each template → iterate fillable_sections
   - UPSERT customer_placeholders (customer_id, plan_id, placeholder_key)
       ON CONFLICT: append template_id to template_ids[], keep existing question
   - Copy question, semantic_tags → derive category (see map below)
   - Check customer_profile_data — if answer exists → mark status='collected' immediately

3. Auto-create customer_documents (one per template)

4. Auto-create customer_tasks (one per pending placeholder)
```

### Category Derivation from Semantic Tags

```python
CATEGORY_MAP = {
    "organization": "Company Info",   "identity":  "Company Info",
    "personnel":    "People & Roles", "leadership":"People & Roles",
    "security":     "Security Controls","access":  "Security Controls",
    "risk":         "Risk Management","asset":     "Asset Management",
    "incident":     "Incident Management",
    "audit":        "Audit & Compliance",
    "supplier":     "Third Parties",  "legal":     "Legal & Regulatory",
}
# First matching tag wins; default = "General"
```

### Deduplication Logic

`{{organization_name}}` appears in 12 templates → **1 placeholder row**, answered once, fills all 12.

Cross-plan reuse: answer `organization_name` for ISO 27001 → assign ISO 27017 → `seed_placeholders()` checks `customer_profile_data` → marks it `collected` immediately. Customer never asked the same question twice.

---

## 5. Customer Workspace UI

### Layout

```
Customer Workspace
├── Header: customer name · status · assigned consultant · overall progress ring
├── Left sidebar: ISO Plans list (progress ring per plan)
└── Main panel (per selected plan):
    ├── Overview tab    — completion %, docs ready, pending count, recent activity
    ├── Questions tab   — smart grouped questionnaire (the core UX)
    ├── Documents tab   — list of docs with per-doc fill %
    └── Activity tab    — timeline: who answered what, when, via which channel
```

### Questions Tab — Smart Questionnaire

**UX rules:**
- Grouped by category (Company Info → People & Roles → Security Controls → ...)
- Already-answered fields shown pre-filled with ✓ badge — user confirms or edits
- "Used in N documents" shown on each answer — user understands impact
- Progress bar per category
- Filter: All / Pending / Answered / Needs Review

**Question card:**
```
┌──────────────────────────────────────────────────────────────┐
│ 🏢 Company Info                                    3 / 5 ✓   │
├──────────────────────────────────────────────────────────────┤
│ What is the full legal name of your organization?            │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Acme Corp Ltd                                            │ │
│ └──────────────────────────────────────────────────────────┘ │
│ Used in 8 documents · Source: manual · ✓ Verified            │
└──────────────────────────────────────────────────────────────┘
```

### Progress Calculation

```
plan_completion     = collected_placeholders / total_placeholders * 100
document_completion = filled_placeholders_in_doc / total_in_doc * 100
                      (already computed by existing DB trigger)
```

---

## 6. Collection Channels

### Channel Types

| Type | How it works | Phase |
|---|---|---|
| `manual` | Admin fills on behalf of customer in workspace | 1 |
| `share_link` | Tokenized URL — customer fills their own form, no login needed | 1 |
| `email` | AI reads inbound emails, extracts answers | 2 |
| `chat` | AI-driven chat (web widget or WhatsApp) | 2 |
| `folder` | Watch shared folder (Google Drive, S3) for uploaded files | 2 |

### Share Link Flow (Phase 1)

```
Admin clicks "Send to Customer"
  → generate share_token (UUID, 30-day expiry)
  → customer receives: https://app.dna.io/collect/{token}
  → no login required — token scoped to one plan only
  → customer sees only their pending questions (no admin UI)
  → on submit → writes to customer_profile_data (source='customer_portal')
  → DB trigger auto-fills all documents
```

Security: token is rate-limited, expires, scoped to one plan, invalidated after completion.

### Email Collection Flow (Phase 2)

```
Inbound email → CollectionAgent
  → extract (field_key, value, confidence) pairs
  → confidence ≥ 0.90 → auto-write (source='email_ai', verified=false)
  → confidence 0.70–0.89 → write as draft, create review task for admin
  → confidence < 0.70 → create task with suggestion, require human confirmation
  → reply to customer confirming what was captured
```

`collected_via_channel_id` on `customer_profile_data` already tracks this — no schema change needed.

---

## 7. AI-Driven Collection Architecture (Phase 2)

### New Service: `dna-collector`

Separate Python worker (same pattern as `dna-ai-service`):
- Polls `collection_channels` for new inputs
- Runs `CollectionAgent` per channel type
- Writes to `customer_profile_data` with confidence + source
- Publishes progress events via Redis

### CollectionAgent Design

```python
class CollectionAgent(BaseAgent):
    """
    Given:  customer context + list of pending placeholder questions
    Input:  raw text (email body, chat message, document text)
    Output: [{placeholder_key, extracted_value, confidence, evidence_snippet}]
    """
```

The agent receives the full list of pending questions — it maps extracted values to known expected fields. This grounds extraction and prevents hallucination.

### Confidence Tiers

| Confidence | Action |
|---|---|
| ≥ 0.90 | Auto-fill, `verified=false`, notify admin |
| 0.70–0.89 | Fill as draft, create admin review task |
| < 0.70 | Create task with suggestion, require human confirmation |

---

## 8. API Design

### Phase 1

```
POST  /api/v1/customers/{id}/plans                        assign ISO plan (seeds placeholders + docs)
GET   /api/v1/customers/{id}/workspace                    full workspace (plans + progress)
GET   /api/v1/customers/{id}/plans/{plan_id}/questions    grouped pending questions
PUT   /api/v1/customers/{id}/profile                      upsert answer(s) → triggers auto-fill
GET   /api/v1/customers/{id}/plans/{plan_id}/progress     completion stats

POST  /api/v1/customers/{id}/plans/{plan_id}/share-link   generate share token
GET   /api/v1/collect/{token}                             public: get questions (no auth)
POST  /api/v1/collect/{token}                             public: submit answers (no auth)
```

### Phase 2 Additions

```
POST  /api/v1/customers/{id}/channels                     create collection channel
GET   /api/v1/customers/{id}/channels                     list channels
POST  /api/v1/channels/{id}/trigger                       manually trigger AI extraction
GET   /api/v1/customers/{id}/profile/history              audit trail of all changes
```

---

## 9. Edge Cases & Robustness

| Scenario | Handling |
|---|---|
| New templates added to ISO after plan assigned | `seed_placeholders()` is idempotent — safe to re-run anytime |
| Answer updated after documents created | Trigger re-runs, all docs re-filled, old value logged |
| Same ISO in two languages for one customer | Drop `unique_active_iso_per_customer`, key on `(customer_id, iso_standard_id, language)` |
| Conflicting answers from two channels | Flag conflict, admin resolves, winning value written with `verified=true` |
| Customer submits share link after expiry | 410 Gone response, admin can regenerate |
| Placeholder key renamed in template | Old key stays collected, new key seeded as pending — no data loss |
| Customer has zero templates in plan | Workspace shows plan with 0 questions, 100% complete |

---

## 10. Top 3 Killer Features

### 🥇 1. Smart Interview Mode (AI-Guided Conversational Collection)

Instead of a static form, an AI agent conducts a **conversational interview**:

- Asks questions in natural language, adapts based on previous answers
- If customer says "we use Azure AD" → auto-fills `ad_directory`, `identity_provider`, `sso_provider` from that single statement
- Detects contradictions and asks for clarification
- Generates a **summary report** at the end: "Here's what we captured — please review before we proceed"
- Works via web chat, WhatsApp, or email thread

**Why it's a killer feature:** Reduces collection from days of back-and-forth to a 30-minute conversation. Customers hate forms. A conversation feels like talking to a consultant — which is exactly what DNA replaces.

**Implementation path:** `interview_sessions` table + streaming chat endpoint + `CollectionAgent` that maps conversation turns to placeholder keys in real time.

---

### 🥈 2. Evidence Vault with Auto-Linking

Many ISO placeholders aren't text — they're documents: org charts, risk registers, network diagrams, existing policies.

- Customer uploads files to their **Evidence Vault** (drag & drop or folder sync)
- AI scans each file → extracts relevant placeholder values automatically
- Links the file as evidence for specific ISO controls (e.g. org chart → fills `ciso_role`, `security_team_structure`)
- Auditor view: "This value came from this document, uploaded on this date, by this person"
- Supports PDF, Word, Excel, images (OCR)

**Why it's a killer feature:** ISO auditors need evidence, not just text answers. This turns the collection process into audit preparation simultaneously — zero extra work for the customer. It also means DNA can ingest existing documentation from day one rather than starting from scratch.

**Implementation path:** `evidence_files` table + file upload endpoint + extraction agent with document parsing + vision/OCR for scanned files.

---

### 🥉 3. Compliance Gap Radar

After placeholders are collected, run an AI gap analysis:

- Compare customer's answers against ISO control requirements
- Flag gaps: "Your incident response SLA is 72 hours — ISO 27001 clause 6.1.2 requires 24 hours"
- Severity tiers: Critical (blocks certification) / Major / Minor / Advisory
- Remediation suggestions per gap: "Update your Incident Response Policy to reflect a 24-hour SLA"
- Track gap closure over time — re-run after each profile update
- Export as a formal **Gap Assessment Report** (PDF)

**Why it's a killer feature:** This is what consultants charge €5,000–€20,000 for. Automating it means DNA delivers consultant-level insight at zero marginal cost per customer. It also creates a clear upsell path: "You have 3 critical gaps — here's how to fix them."

**Implementation path:** `gap_analyses` table + gap analysis agent that takes `customer_profile_data` + ISO requirements text → structured gap report with severity + remediation. Runs as a background task after each profile update.

---

## 11. Implementation Phases

### Phase 1 — Manual Collection (2–3 weeks)
- [ ] Schema additions (question, category, collection_channels)
- [ ] `seed_placeholders()` on plan assignment
- [ ] Auto-create customer_documents on assignment
- [ ] Customer Workspace UI (progress rings + grouped questionnaire)
- [ ] `PUT /profile` endpoint with trigger propagation
- [ ] Share link generation + public collection form (no login)

### Phase 2 — Automated Collection (4–6 weeks)
- [ ] `dna-collector` service skeleton
- [ ] Email channel (inbound parsing via CollectionAgent)
- [ ] Confidence-based auto-fill with review queue
- [ ] Answer conflict resolution UI
- [ ] Profile data history / audit trail

### Phase 3 — Intelligence Layer (6–8 weeks)
- [ ] Smart Interview Mode (streaming chat + real-time extraction)
- [ ] Evidence Vault (file upload + AI extraction)
- [ ] Compliance Gap Radar (gap analysis agent + report export)
- [ ] Cross-customer benchmarking ("most companies your size answer X for this field")
