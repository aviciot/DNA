# DNA — Customer Data Collection Platform

## Vision

DNA helps ISO certification consultants manage customers through the certification process.

When a customer is assigned an ISO plan, DNA must collect all data needed to fill every `{{placeholder}}` across every template in that plan — each unique data point collected **once**, propagated to every document automatically.

**End goal:** what takes consultants weeks of back-and-forth gets done through automated channels (email AI, customer portal, AI chat), with documents auto-filled and ready to go.

**All development must consider this multi-channel automation vision**, even when building manual-first features.

---

## Architecture

```
iso_standards
  └── templates  (master templates with {{placeholders}})
        └── template_iso_mapping

customer_iso_plans  (customer enrolled in an ISO)
  └── customer_documents  (per-customer COPY of each template — fully customizable)
        └── customer_placeholders  (UNIQUE customer+plan+key — deduped across templates)
              └── customer_profile_data  (ONE value per field_key per customer — shared across ALL plans)
```

`customer_profile_data` is the **single source of truth**. Answer `{{organization_name}}` once — it propagates to every document across every plan. Answer it for ISO 27001 → assign ISO 27017 → already marked collected. Customer never asked twice.

### Customer Document Copy
When a customer is assigned a plan, each template is copied into `customer_documents` as a **customer-specific instance**. This copy can be fully customized (placeholders, sections, questions) without affecting the master template or other customers.

---

## What's Built ✅

- Customer creation with portal credentials and storage
- ISO plan assignment
- `seed_placeholders()` — deduplicates across templates, checks existing profile data, marks collected immediately
- `customer_placeholders` schema: `question`, `category`, `hint`, `example_value`, `semantic_tags`
- `customer_profile_data.display_label`
- `customer_collection_channels` table (ready for Phase 2)
- `customer_task_resolutions` table
- Auto-create `customer_documents` on plan assignment
- Auto-generate tasks per document from fillable sections
- Customer workspace UI: Documents / Tasks / Progress / Coverage tabs

---

## What's Missing — The Collection Loop ❌

Placeholders are seeded correctly but **there is no way to answer them yet**:
- No API to upsert answers into `customer_profile_data`
- No API to return grouped questions per plan
- No propagation from `customer_profile_data` → `customer_documents` (trigger or service)
- No Questions/Interview UI in the workspace

---

## Current Focus — Interview Interface (Phase 1)

### What it is
A DNA user (consultant) opens a customer's workspace, selects a document, and gets a structured interview interface to fill in all placeholders — during or after a customer call.

### DNA User Can:
- **Answer placeholders** — fill in values field by field, one answer propagates to all documents that use it
- **Customize the template copy** for this specific customer:
  - Edit question text, hint, example value per placeholder
  - Add new placeholders not in the master template
  - Remove irrelevant sections
  - Reorder sections
  - Change section titles and descriptions
- **Track progress** — see which placeholders are answered, pending, or need review
- **Filter** — All / Pending / Answered / Needs Review

### Future: AI-Assisted Fill (planned, not now)
The dashboard has a chat widget — a future MCP tool will let the DNA user paste interview notes and AI extracts answers automatically. Architecture must support this (answers written via same `PUT /profile` endpoint regardless of source).

### Question Card UI
```
┌─────────────────────────────────────────────────────┐
│ 🏢 Company Info                           3 / 5 ✓   │
├─────────────────────────────────────────────────────┤
│ What is the full legal name of your organization?   │
│ ┌───────────────────────────────────────────────┐   │
│ │ Acme Corp Ltd                                 │   │
│ └───────────────────────────────────────────────┘   │
│ Used in 8 documents · Source: manual · ✓ Verified   │
└─────────────────────────────────────────────────────┘
```

### API Needed
```
GET  /api/v1/customers/{id}/plans/{plan_id}/questions     grouped questions by category
PUT  /api/v1/customers/{id}/profile                       upsert answer → propagate to all docs
PUT  /api/v1/customers/{id}/documents/{doc_id}/template   update customer's template copy
```

### Progress Calculation
```
plan_completion     = collected_placeholders / total_placeholders * 100
document_completion = filled_placeholders_in_doc / total_in_doc * 100
```

---

## Collection Channels (Phase 2)

| Channel | How | Status |
|---|---|---|
| `manual` | DNA user fills on behalf of customer (current focus) | 🔨 Building |
| `share_link` | Tokenized URL — customer fills their own form, no login | 📋 Planned |
| `email` | AI reads inbound emails, extracts answers | 📋 Planned |
| `chat` | AI-driven chat widget (web / WhatsApp) | 📋 Planned |
| `folder` | Watch shared folder for uploaded files | 📋 Planned |

All channels write to `customer_profile_data` via the same endpoint — source tracked via `source` + `collected_via_channel_id`.

### Email AI Flow (Phase 2)
```
Inbound email → CollectionAgent
  → extract (field_key, value, confidence)
  → ≥ 0.90  → auto-write (source='email_ai', verified=false)
  → 0.70–0.89 → draft, create admin review task
  → < 0.70  → task with suggestion, require human confirmation
```

---

## Future Intelligence Layer (Phase 3)

- **Smart Interview Mode** — AI conducts conversational interview, maps answers to placeholders in real time. "We use Azure AD" → auto-fills `ad_directory`, `identity_provider`, `sso_provider`.
- **Evidence Vault** — customer uploads files, AI extracts placeholder values, links file as audit evidence.
- **Compliance Gap Radar** — AI compares collected answers against ISO requirements, flags gaps with severity + remediation suggestions, exports Gap Assessment Report.

---

## Implementation Phases

### Phase 1 — Manual Collection (current)
- [x] Schema: `customer_placeholders` enriched columns
- [x] `seed_placeholders()` on plan assignment
- [x] Auto-create `customer_documents` on assignment
- [x] Auto-generate tasks per document
- [ ] `GET /plans/{plan_id}/questions` — grouped questions API
- [ ] `PUT /profile` — upsert answer + propagate to documents
- [ ] `PUT /documents/{doc_id}/template` — customer template customization
- [ ] Interview UI in customer workspace (Questions tab)
- [ ] Template editor UI (add/remove/edit placeholders and sections)

### Phase 2 — Automated Collection
- [ ] Share link + public collection form
- [ ] Email channel (CollectionAgent)
- [ ] Confidence-based auto-fill with review queue
- [ ] Answer conflict resolution UI
- [ ] Profile data history / audit trail

### Phase 3 — Intelligence Layer
- [ ] Smart Interview Mode (AI chat → real-time extraction via MCP)
- [ ] Evidence Vault (file upload + AI extraction)
- [ ] Compliance Gap Radar (gap analysis agent + PDF report)
