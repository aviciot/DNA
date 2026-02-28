# Customer Data Model — DNA Platform

## Overview

A **customer** is a company being certified. The full lifecycle:

```
customers
  └── customer_iso_plans          (assigned ISO standards)
        └── customer_iso_plan_templates   (which templates are in scope)
        └── customer_documents            (one doc per template — customer's editable copy)
        └── customer_placeholders         (deduplicated questions for the plan)
              └── customer_profile_data   (the answers — shared pool across plans)
        └── customer_tasks                (work items to collect each answer)
              └── task_resolutions        (how each task was resolved)
  └── customer_configuration      (flexible key/value config per customer)
```

---

## Data Preparation — How a Customer Gets Their Workspace

### The core idea

Master templates (`templates.template_structure`) are blueprints — they never change.
When a customer is assigned an ISO plan, we **copy** each template's content into `customer_documents.content`.
That copy is the customer's own editable document. The DNA user works only on that copy.

### Why copy instead of reference?

- Each customer may have different answers, hidden sections, or customized text
- The master template can be updated without affecting in-progress customer work
- Completion % and fill status are tracked per customer, not per template

### Seeding flow (runs once at plan creation)

```
For each template in the plan:

  1. COPY template_structure → customer_documents.content
     One document row per template. Status = not_started.

  2. SCAN content for {{placeholders}} → UPSERT customer_placeholders
     Deduplicated by placeholder_key across all templates in the plan.
     {{company_name}} in 12 templates = 1 row, template_ids[] has all 12.
     If customer_profile_data already has an answer → status = collected immediately.

  3. For each mandatory/evidence section → INSERT customer_tasks
     One task per section that needs an answer or evidence.
     placeholder_key links the task to its placeholder.
```

### What triggers the seeding?

`generate_documents_for_plan()` in `document_generator_service.py` — called from `iso_customers.py` after plan + templates are inserted.
This is the single entry point for both customer creation and adding a new ISO plan from the workspace.

### Answer flow (after seeding)

```
DNA user submits answer for placeholder_key
  → UPSERT customer_profile_data          (the answer, shared across plans)
  → UPDATE customer_placeholders.status = 'collected'
  → trigger: customer_tasks.status = 'completed'
  → trigger: customer_documents.content updated + completion_percentage recalculated
```

Same flow regardless of channel (manual workspace, customer portal, email AI).

---

## Table Reference

### `dna_app.customers` — Core customer record

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK, serial) | Auto-increment |
| `name` | varchar(255) | Company name — required |
| `email` | varchar(255) | Primary email |
| `contact_person` | varchar(255) | Main contact name |
| `phone` | varchar(50) | |
| `address` | text | |
| `website` | varchar(500) | |
| `description` | text | Optional notes |
| `status` | varchar(50) | `active` \| `inactive` \| `pending` \| `completed` |
| `portal_username` | varchar(100) | **UNIQUE** — customer portal login |
| `portal_password_hash` | varchar(255) | Hashed portal password |
| `portal_enabled` | boolean | Enable/disable portal access |
| `last_portal_login` | timestamp | |
| `contact_email` | varchar(255) | Primary contact email |
| `document_email` | varchar(255) | Email for sending/receiving docs |
| `compliance_email` | varchar(255) | For evidence/document automation |
| `contract_email` | varchar(255) | For CISO/Legal |
| `storage_type` | varchar(50) | `local` \| `google_drive` \| `s3` |
| `storage_path` | varchar(500) | Path/URL to customer storage |
| `storage_config` | jsonb | Credentials, bucket names, etc. |
| `metadata` | jsonb | Flexible extra data |
| `created_by` | integer → `auth.users.id` | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | Auto-updated by trigger |

**Constraints:** `status` must be one of the 4 valid values. `portal_username` is unique.

---

### `dna_app.customer_iso_plans` — ISO plan assigned to a customer

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `customer_id` | integer → `customers.id` | CASCADE delete |
| `iso_standard_id` | uuid → `iso_standards.id` | RESTRICT delete |
| `plan_name` | varchar(255) | e.g. "ISO 27001 Certification 2025" |
| `plan_status` | varchar(50) | `active` \| `paused` \| `completed` \| `cancelled` |
| `template_selection_mode` | varchar(50) | `all` \| `selective` |
| `target_completion_date` | date | |
| `started_at` | timestamp | |
| `completed_at` | timestamp | |
| `is_ignored` | boolean | Soft-ignore (kept for history) |
| `ignored_at` / `ignored_by` / `ignore_reason` | — | Audit trail |
| `created_by` | integer → `auth.users.id` | |
| `created_at` / `updated_at` | timestamp | |

**Constraint:** `UNIQUE(customer_id, iso_standard_id)` — one plan per ISO per customer.

---

### `dna_app.customer_iso_plan_templates` — Templates in scope for a plan

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `plan_id` | uuid → `customer_iso_plans.id` | CASCADE delete |
| `template_id` | uuid → `templates.id` | RESTRICT delete |
| `included` | boolean | Default true |
| `is_ignored` | boolean | Soft-ignore |
| `ignored_at` / `ignored_by` / `ignore_reason` | — | Audit trail |
| `created_at` | timestamp | |

**Constraint:** `UNIQUE(plan_id, template_id)`

Used only when `template_selection_mode = 'selective'`. In `all` mode, templates are resolved via `template_iso_mapping`.

---

### `dna_app.customer_documents` — One document per template per plan

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `customer_id` | integer → `customers.id` | CASCADE delete |
| `plan_id` | uuid → `customer_iso_plans.id` | CASCADE delete |
| `template_id` | uuid → `templates.id` | RESTRICT delete |
| `template_name` | varchar(500) | Snapshot at creation |
| `document_name` | varchar(500) | |
| `document_type` | varchar(100) | |
| `iso_code` | varchar(50) | |
| `status` | varchar(50) | `not_started` \| `in_progress` \| `pending_review` \| `approved` \| `rejected` |
| `completion_percentage` | integer | 0–100, auto-computed by DB trigger |
| `placeholder_fill_status` | jsonb | `{key: "filled"\|"pending"}` — updated by trigger |
| `last_auto_filled_at` | timestamp | Last trigger run |
| `content` | jsonb | Full document structure |
| `assigned_to` | integer → `auth.users.id` | |
| `due_date` | date | |
| `notes` | text | |
| `created_at` / `updated_at` | timestamp | |

**Constraint:** `UNIQUE(customer_id, plan_id, template_id)` — one doc per template per plan.

**Trigger:** `trg_placeholder_to_document` — when a `customer_placeholder` status changes to `collected`, this trigger updates `placeholder_fill_status` and recalculates `completion_percentage`.

---

### `dna_app.customer_placeholders` — Deduplicated questions per plan

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `customer_id` | integer → `customers.id` | CASCADE delete |
| `plan_id` | uuid → `customer_iso_plans.id` | CASCADE delete |
| `placeholder_key` | varchar(255) | e.g. `organization_name` |
| `display_label` | varchar(500) | Human-readable label |
| `data_type` | varchar(50) | `text` (default) |
| `is_required` | boolean | Default true |
| `status` | varchar(50) | `pending` \| `collected` \| `auto_filled` |
| `profile_data_id` | uuid → `customer_profile_data.id` | SET NULL on delete |
| `template_ids` | uuid[] | All templates that use this placeholder |
| `collected_at` | timestamp | |
| `created_at` | timestamp | |

**Constraint:** `UNIQUE(customer_id, plan_id, placeholder_key)` — one row per question per plan.

**Key concept:** `{{organization_name}}` in 12 templates = 1 row here. Answer once → fills all 12.

**Triggers:**
- `trg_placeholder_to_task` — when status changes, syncs linked `customer_tasks`
- `trg_placeholder_to_document` — when status changes, updates `customer_documents`

---

### `dna_app.customer_profile_data` — Shared answer pool per customer

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `customer_id` | integer → `customers.id` | CASCADE delete |
| `field_key` | varchar(255) | Matches `placeholder_key` |
| `field_value` | text | The actual answer |
| `file_path` | varchar(1000) | If answer is a file |
| `file_mime_type` | varchar(100) | |
| `data_type` | varchar(50) | `text` (default) |
| `source` | varchar(50) | `manual` \| `customer_portal` \| `email_ai` |
| `confidence` | smallint | 100 = confirmed, <100 = AI inferred |
| `verified` | boolean | Admin-verified flag |
| `collected_via_channel_id` | uuid | Which channel provided this answer |
| `created_at` / `updated_at` | timestamp | |

**Constraint:** `UNIQUE(customer_id, field_key)` — one answer per field per customer (cross-plan).

**Key concept:** Answers are shared across plans. Answer `organization_name` for ISO 27001 → assign ISO 27017 → already marked `collected`.

---

### `dna_app.customer_tasks` — Work items to collect placeholder values

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `customer_id` | integer → `customers.id` | CASCADE delete |
| `plan_id` | uuid → `customer_iso_plans.id` | CASCADE delete |
| `document_id` | uuid → `customer_documents.id` | CASCADE delete |
| `template_id` | uuid → `templates.id` | CASCADE delete |
| `placeholder_key` | varchar(255) | Which `{{placeholder}}` this collects |
| `task_type` | varchar(50) | `fillable_section` \| `evidence_required` \| `review` \| `custom` \| `interview` |
| `task_scope` | varchar(50) | `document` \| `customer` \| `iso_plan` |
| `title` | varchar(500) | |
| `description` | text | |
| `status` | varchar(50) | `pending` \| `in_progress` \| `blocked` \| `completed` \| `cancelled` |
| `priority` | varchar(50) | `low` \| `medium` \| `high` \| `urgent` |
| `answer` | text | Collected answer |
| `answered_at` | timestamp | |
| `answered_via` | varchar(50) | Channel used |
| `requires_evidence` | boolean | |
| `evidence_files` | jsonb | |
| `assigned_to` | integer → `auth.users.id` | |
| `due_date` | date | |
| `auto_generated` | boolean | true = system-generated, false = manual |
| `is_ignored` | boolean | Soft-ignore |
| `created_at` / `updated_at` | timestamp | |

**Trigger:** `trg_task_to_placeholder` — when task status → `completed`, syncs `customer_placeholders` status to `collected`.

---

### `dna_app.task_resolutions` — How a task was resolved

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `task_id` | uuid → `customer_tasks.id` | CASCADE delete |
| `resolution_type` | varchar(50) | |
| `resolution_data` | jsonb | |
| `is_final` | boolean | |
| `requires_approval` | boolean | |
| `approved_at` / `approved_by` | — | |
| `quality_score` | integer | 1–5 |
| `completeness_score` | integer | 0–100 |
| `resolved_by` | integer → `auth.users.id` | |
| `resolved_at` | timestamp | |
| `attachments` | jsonb | |
| `notes` | text | |

---

### `dna_app.customer_configuration` — Flexible config per customer

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `customer_id` | integer → `customers.id` \| NULL | NULL = global default |
| `config_type` | varchar(100) | Category of config |
| `config_key` | varchar(255) | Specific key |
| `config_value` | jsonb | The value |
| `is_active` | boolean | |
| `is_default` | boolean | |
| `use_ai_phrasing` | boolean | AI-generated content flag |
| `created_at` / `updated_at` | timestamp | |

**Constraint:** `UNIQUE(customer_id, config_type, config_key)`

---

## Trigger Chain (Auto-fill Flow)

```
customer_tasks.status → 'completed'
  ↓ trg_task_to_placeholder
customer_placeholders.status → 'collected'
  ↓ trg_placeholder_to_task   (syncs other tasks with same key)
  ↓ trg_placeholder_to_document
customer_documents.placeholder_fill_status updated
customer_documents.completion_percentage recalculated
```

---

## Useful Views

| View | Purpose |
|---|---|
| `v_customer_iso_progress` | Per-plan stats: total/completed templates, tasks, progress % |
| `v_customer_overall_progress` | Per-customer rollup: plans, docs, tasks, avg completion |

---

## Backend Endpoints

### Customer — `iso_customers.py` → `/api/v1/iso-customers`

> **Single source of truth for all customer operations.** `customer_management.py` was deleted.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `` | operator/admin | Create customer with portal credentials, storage, and optional ISO assignments. Calls `generate_documents_for_plan()` inline. |
| `GET` | `` | any auth | List all customers with plan/doc counts. |
| `GET` | `/{id}` | any auth | Single customer with stats. |
| `PUT` | `/{id}` | operator/admin | Update customer fields. |
| `DELETE` | `/{id}` | admin | Hard delete (blocks if ISO plans exist). |
| `POST` | `/{id}/reset-password` | admin | Reset portal password. |

### ISO Plans — `iso_plans.py` → `/api/v1/iso-plans`

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `` | admin | Create plan. Fields: `customer_id`, `iso_standard_id`, `plan_name`, `template_selection_mode` (`all`\|`selective`), `selected_template_ids[]`, `target_completion_date`, `auto_generate_documents`. |
| `GET` | `/customer/{customer_id}` | any auth | List plans for customer. |
| `GET` | `/{plan_id}` | any auth | Single plan. |
| `GET` | `/{plan_id}/generation-preview` | any auth | Preview what docs/tasks will be generated. |
| `POST` | `/{plan_id}/generate-documents` | admin | Generate all documents + tasks for plan. |
| `DELETE` | `/{plan_id}` | admin | Hard delete plan + cascade. |

---

## Create Customer Flow

### Required fields
- `name`, `email`

### Optional fields
- `contact_person`, `phone`, `website`, `address`, `description`, `compliance_email`, `contract_email`
- **Portal access:** `portal_username` + `portal_password` (hashed by backend), `portal_enabled=true`
- **ISO assignments:** `iso_assignments[]` — each with `iso_standard_id`, `template_selection_mode`, optional `selected_template_ids[]`

### What happens on `POST /api/v1/iso-customers`
```
1. INSERT customers row (with hashed portal password if provided)
2. Initialize storage folder on disk
3. For each iso_assignment:
   a. INSERT customer_iso_plans  (plan_status = 'active')
   b. INSERT customer_iso_plan_templates
   c. generate_documents_for_plan():
      - INSERT customer_documents  (one per template)
      - UPSERT customer_placeholders  (deduplicated)
      - INSERT customer_tasks  (one per fillable section)
```

### Portal credentials
Portal login is separate from `auth.users` — stored directly on the `customers` row.
Password is bcrypt-hashed by the backend. Plain password returned once in the response.

---

## Access Control

| Operation | Auth |
|---|---|
| Create / Edit customer | operator or admin |
| Delete customer | admin only |
| View customers | any auth |
| Assign / Delete ISO plan | admin only |

---

## Dead Schema

- **`customer_task_templates`** — dropped. Was empty, no backend references, no defined purpose.

---

## Gaps (not yet built)

1. **Workspace API** — `GET /customers/{id}/workspace` not implemented
2. **Questions API** — `GET /customers/{id}/plans/{plan_id}/questions` not implemented
3. **Profile upsert** — `PUT /customers/{id}/profile` not implemented (writes answers, triggers auto-fill)
