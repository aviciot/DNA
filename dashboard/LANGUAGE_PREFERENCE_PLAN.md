# Language Preference — Implementation Plan

## Goal

Add a `preferred_language` property to every customer that controls:
- All outbound communication emails (welcome, notifications, ISO360 reminders, announcements)
- ISO360 KYC questionnaire generation and activity personalisation

ISO plan documents are **not** in scope — they are a structural copy of English templates with no LLM involved at generation time.

Supported values: `"en"` (English) | `"he"` (Hebrew)

---

## Architecture Decision

**Single source of truth: `customers.preferred_language`**

- `customer_automation_config.preferred_language` already exists and already works for collection/follow-up emails — it stays as-is (no change, no removal)
- For everything else (welcome, notifications, ISO360), we read from `customers.preferred_language`
- ISO360 plans get their own `preferred_language` column on `customer_iso_plans`, defaulting to the customer value at plan creation time, overridable per-plan

---

## What Is Already Working (No Change Needed)

| Flow | Status |
|---|---|
| Collection campaign emails | ✅ Language flows: backend → Redis `automation:send` → `send_campaign_email` |
| Follow-up emails | ✅ Scheduler reads `customer_automation_config.preferred_language` and injects into Redis |
| Extraction reply emails | ✅ `stream_consumer.py` reads `cfg_customer.preferred_language` from `customer_automation_config` |

---

## What Needs to Change

### 1. Database — Migration

**File to create:** `dashboard/migrations/028_customer_preferred_language.sql`

```sql
-- Add preferred_language to customers table
ALTER TABLE dna_app.customers
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5) NOT NULL DEFAULT 'en';

-- Add per-plan language override to customer_iso_plans (NULL = inherit from customer)
ALTER TABLE dna_app.customer_iso_plans
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5) NULL;
```

---

### 2. Backend — `iso_customers.py`

**Path:** `dashboard/backend/app/routes/iso_customers.py`

**Changes:**

a) Add `preferred_language: str = "en"` to `ISOCustomerCreate`

b) Add `preferred_language: Optional[str] = None` to `ISOCustomerUpdate`

c) In `create_iso_customer` INSERT query — include `preferred_language` column

d) In `create_iso_customer`, when inserting `welcome_customer` notification task — inject language into description JSON:
```python
# Read preferred_language from the newly created customer_row
lang = customer_data.preferred_language or "en"

# welcome_customer task description (currently has no description)
# Change the INSERT to include description with language:
description=json.dumps({"language": lang})

# welcome_plan task description already has JSON — add "language" key:
_notification_json.dumps({
    "iso_code": ...,
    "iso_name": ...,
    ...existing fields...,
    "language": lang,
})
```

e) In `create_iso_customer`, when calling `plan_row INSERT` — set `preferred_language = customer_data.preferred_language`

f) In `update_iso_customer` UPDATE query — include `preferred_language` if provided

---

### 3. Backend — `iso360_customer.py`

**Path:** `dashboard/backend/app/routes/iso360_customer.py`

**Changes:**

a) In `trigger_kyc_batch` — fetch `preferred_language` from `customer_iso_plans` (falling back to `customers.preferred_language`) and add to Redis stream:
```python
# Add to the existing plan_row SELECT:
COALESCE(p.preferred_language, c.preferred_language, 'en') AS language

# Add to redis xadd:
"language": plan_row["language"],
```

b) In `check_kyc_completion` — same: fetch language from plan/customer and add `"language"` to the `ai:iso360_adjustment` stream message

c) Add new endpoint `PATCH /{customer_id}/iso360/plans/{plan_id}/language`:
```python
@router.patch("/{customer_id}/iso360/plans/{plan_id}/language")
async def update_plan_language(customer_id: int, plan_id: UUID, language: str, ...):
    # UPDATE customer_iso_plans SET preferred_language = $1 WHERE id = $2 AND customer_id = $3
```

---

### 4. Automation Service — `db_client.py`

**Path:** `DNA/automation-service/db_client.py`

**Two changes:**

a) `get_pending_notification_tasks` — add `c.preferred_language` to the SELECT:
```python
# Current SELECT:
SELECT ct.*, c.name AS customer_name, c.email AS customer_email,
       c.contact_email, c.compliance_email,
       c.description AS customer_description,
       cpa.token AS portal_token

# Change to:
SELECT ct.*, c.name AS customer_name, c.email AS customer_email,
       c.contact_email, c.compliance_email,
       c.description AS customer_description,
       c.preferred_language,
       cpa.token AS portal_token
```

b) `_check_kyc_batch_completion` — fetch `preferred_language` from `customer_iso_plans`/`customers` and add `"language"` to the `ai:iso360_adjustment` xadd call:
```python
# Add to the plan_row SELECT:
COALESCE(p.preferred_language, c.preferred_language, 'en') AS language
# (requires joining customers table)

# Add to r.xadd("ai:iso360_adjustment", {...}):
"language": plan_row["language"],
```

---

### 5. Automation Service — `scheduler.py`

**Path:** `DNA/automation-service/scheduler.py`

**One change — fix the `# TODO`:**

In `_notification_job`, replace:
```python
language = "en"  # TODO: from customer_automation_config
```

With:
```python
language = task.get("preferred_language") or "en"
```

This works because `get_pending_notification_tasks` (change #4a above) now returns `preferred_language` from the customers JOIN.

Also in `_notification_job`, read language from task description JSON when present (welcome_plan tasks carry it there):
```python
# After the existing variables merge from task["description"]:
if isinstance(extra, dict) and "language" in extra:
    language = extra["language"]
```

---

### 6. Frontend — `CustomerCreationWizard.tsx`

**Path:** `dashboard/frontend/src/components/CustomerCreationWizard.tsx`

**Changes:**

a) Add `preferredLanguage: "en"` to `EMPTY_DATA`

b) In `ContactStep` — add language selector after the Storage Type section:
```tsx
<div>
  <label>Communication Language</label>
  <div className="grid grid-cols-2 gap-3">
    {[
      { value: "en", label: "🇬🇧 English" },
      { value: "he", label: "🇮🇱 Hebrew (עברית)" },
    ].map(opt => (
      <button key={opt.value}
        onClick={() => updateData({ preferredLanguage: opt.value })}
        className={`... ${data.preferredLanguage === opt.value ? "selected styles" : "default styles"}`}>
        {opt.label}
      </button>
    ))}
  </div>
  <p className="text-xs text-gray-500">
    All automated emails (welcome, notifications, reminders) will be sent in this language
  </p>
</div>
```

c) In `ReviewStep` — show language in the Contact & Communication summary card

d) In `ReviewStep → handleCreateCustomer` payload — add:
```typescript
preferred_language: data.preferredLanguage || "en",
```

---

### 7. Frontend — `ISO360CustomerTab.tsx`

**Path:** `dashboard/frontend/src/components/admin/ISO360CustomerTab.tsx`

**Change — add per-plan language override in the KYC panel header:**

When `!activePlan.adjustment_pass_done` (KYC panel is showing), display a small language toggle next to the plan name in the header. This lets operators override the language before triggering KYC.

```tsx
// In the KYC panel header area, alongside iso_code display:
<div className="flex items-center gap-2">
  {["en", "he"].map(lang => (
    <button key={lang}
      onClick={() => updatePlanLanguage(activePlan.plan_id, lang)}
      className={`text-xs px-2 py-0.5 rounded font-semibold border
        ${planLanguage === lang
          ? "bg-white text-indigo-700 border-white"
          : "bg-white/20 text-white/70 border-white/30 hover:bg-white/30"}`}>
      {lang === "en" ? "EN" : "HE"}
    </button>
  ))}
</div>
```

Add `planLanguage` state (loaded from plan data or customer default) and `updatePlanLanguage` function that calls `PATCH /{customer_id}/iso360/plans/{plan_id}/language`.

---

## File Change Summary

| # | File | Service | Change Type |
|---|---|---|---|
| 1 | `dashboard/migrations/028_customer_preferred_language.sql` | DB | **New file** |
| 2 | `dashboard/backend/app/routes/iso_customers.py` | Backend | Add field to create/update + seed into welcome task descriptions + plan INSERT |
| 3 | `dashboard/backend/app/routes/iso360_customer.py` | Backend | Pass language in KYC/adjustment Redis messages + new PATCH endpoint |
| 4 | `DNA/automation-service/db_client.py` | Automation | Add `preferred_language` to notification tasks query + fix `_check_kyc_batch_completion` Redis message |
| 5 | `DNA/automation-service/scheduler.py` | Automation | Fix `# TODO` — read language from task row instead of hardcoded `"en"` |
| 6 | `dashboard/frontend/src/components/CustomerCreationWizard.tsx` | Frontend | Language selector in ContactStep + payload |
| 7 | `dashboard/frontend/src/components/admin/ISO360CustomerTab.tsx` | Frontend | Per-plan language toggle in KYC panel |

**Total: 7 files — 1 new, 6 modified**

---

## Implementation Order

1. **Migration first** — everything depends on the DB columns existing
2. **`iso_customers.py`** — customer creation must store the language
3. **`db_client.py`** — notification query must return language before scheduler can use it
4. **`scheduler.py`** — fix the TODO (depends on #3)
5. **`iso360_customer.py`** — KYC/adjustment language (depends on #1)
6. **`CustomerCreationWizard.tsx`** — UI for setting language at creation (depends on #2)
7. **`ISO360CustomerTab.tsx`** — per-plan override UI (depends on #5)

---

## Out of Scope

- ISO plan document content (section titles, fixed prose) — these are structural copies of English templates, no LLM is involved at generation time. Translating them requires parallel Hebrew templates in the DB, which is a content/data task not a code task.
- `customer_automation_config.preferred_language` — already works for collection/follow-up emails, no change needed.
