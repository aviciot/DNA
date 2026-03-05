# Placeholder Dictionary Redesign — Implementation Plan

## Background & Problem Statement

This project is a DNA (Document & Compliance Automation) platform that helps ISO consultants manage
customer certification workflows. The system generates ISO compliance document templates using an LLM
(Gemini), then assigns those templates to customers as "plans". Customers fill in placeholders
(`{{organization_name}}`, `{{ciso_name}}`, etc.) via an Interview tab in the dashboard.

### The Bug Being Fixed

The LLM prompt (`iso_build`) contains an explicit deduplication rule:
> "FILLABLE_SECTIONS DEDUPLICATION RULE — Define each placeholder FULLY only in the FIRST template
> where it appears. In subsequent templates, OMIT fillable_sections entries."

This means `fillable_sections` (which contains question/label/category metadata for each `{{key}}`)
is only defined in the first template that uses a key. When a customer is assigned a partial set of
templates (not all templates in the plan), `seed_placeholders` misses keys whose metadata only lives
in templates not included in the customer's plan. Result: Interview tab shows missing questions.

The current workaround in `task_generator_service.py` does a cross-template fallback lookup, but it's
fragile and doesn't handle all edge cases.

### The Fix

Replace `fillable_sections` per-template with a single `placeholder_dictionary` generated once per
ISO standard build. The LLM outputs a top-level `placeholder_dictionary` array covering ALL keys
across ALL templates, with canonical normalized keys. This dictionary is stored on `iso_standards`
and copied to each customer plan when the plan is created.

---

## Infrastructure & Environment

### Docker Services
- `dna-frontend` — Next.js dashboard (port 3007)
- `dna-backend` — FastAPI backend (port 3010)
- `dna-postgres` — PostgreSQL (port 5432, internal)
- `dna-redis` — Redis (port 6379, internal)
- `dna-ai-service` — Python AI worker (consumes Redis streams)

### Rebuild after changes
```bash
docker compose build dna-frontend dna-backend dna-ai-service && docker compose up -d dna-frontend dna-backend dna-ai-service
```

### Database Connection
- Host: `dna-postgres` (internal Docker network) or `localhost:5432` (from host)
- Database: `dna`
- User: `dna_user`
- App schema: `dna_app`
- Auth schema: `auth`
- Connect from host: `docker exec dna-postgres psql -U dna_user -d dna`

### Key Config
- Backend DB pool: `DNA/dashboard/backend/app/database.py` — uses `settings.DATABASE_APP_SCHEMA` = `dna_app`
- AI service DB: `DNA/ai-service/db_client.py` — same pool pattern
- All SQL uses schema prefix: `{settings.DATABASE_APP_SCHEMA}.table_name`

---

## Relevant Files

| File | Purpose |
|------|---------|
| `DNA/db/init/01-init.sql` | Full DB schema dump — reference for all table structures |
| `DNA/dashboard/migrations/` | Migration files (run manually via psql) |
| `DNA/ai-service/stream_consumer.py` | Redis stream consumer — `_handle_iso_build_task()` saves ISO standard + templates |
| `DNA/ai-service/agents/iso_builder.py` | `ISOBuilderAgent.build_from_pdf()` — calls LLM, returns `{summary, templates}` |
| `DNA/ai-service/db_client.py` | DB helper used by AI service |
| `DNA/dashboard/backend/app/routes/iso_customers.py` | `create_iso_customer()` — creates `customer_iso_plans` and calls `generate_documents_for_plan()` |
| `DNA/dashboard/backend/app/services/task_generator_service.py` | `seed_placeholders()` — the function being simplified |
| `DNA/dashboard/backend/app/routes/iso_builder.py` | FastAPI route that queues `iso:build` Redis stream message |

---

## Relevant DB Tables (from `DNA/db/init/01-init.sql`)

### `dna_app.iso_standards`
```
id UUID PK, code VARCHAR(50), name VARCHAR(200), description TEXT,
requirements_summary TEXT, active BOOLEAN, color VARCHAR(7),
ai_metadata JSONB, tags TEXT[], language VARCHAR(5)
```
→ **Add column**: `placeholder_dictionary JSONB DEFAULT '[]'`

### `dna_app.customer_iso_plans`
```
id UUID PK, customer_id INT FK→customers, iso_standard_id UUID FK→iso_standards,
plan_name VARCHAR(255), plan_status VARCHAR(50), template_selection_mode VARCHAR(50),
target_completion_date DATE, started_at TIMESTAMP, created_by INT, created_at TIMESTAMP
```

### `dna_app.customer_placeholders`
```
id UUID PK, customer_id INT, plan_id UUID FK→customer_iso_plans,
placeholder_key VARCHAR(255), display_label VARCHAR(500), question TEXT,
category VARCHAR(100), hint TEXT, example_value TEXT, semantic_tags TEXT[],
data_type VARCHAR(50), is_required BOOLEAN, status VARCHAR(50),
profile_data_id UUID FK→customer_profile_data, template_ids UUID[]
UNIQUE(customer_id, plan_id, placeholder_key)
```

### `dna_app.templates`
```
id UUID PK, name VARCHAR(255), iso_standard VARCHAR(50),
template_structure JSONB,  ← contains fixed_sections + fillable_sections arrays
status VARCHAR(50), ai_task_id UUID FK→ai_tasks
```

### `dna_app.ai_prompts`
```
id UUID PK, prompt_key VARCHAR(100) UNIQUE, prompt_text TEXT,
model VARCHAR(100), max_tokens INT, temperature NUMERIC, is_active BOOLEAN
```
→ The `iso_build` prompt is stored here. Update via SQL UPDATE.

---

## Implementation Steps

---

### Step 1 — DB Migration

**File to create**: `DNA/dashboard/migrations/008_iso_placeholder_dictionary.sql`

```sql
BEGIN;

-- 1. Add placeholder_dictionary column to iso_standards (master dictionary per standard)
ALTER TABLE dna_app.iso_standards
ADD COLUMN IF NOT EXISTS placeholder_dictionary JSONB DEFAULT '[]';

-- 2. Create per-plan dictionary table (populated when customer plan is created)
CREATE TABLE IF NOT EXISTS dna_app.iso_placeholder_dictionary (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    key         VARCHAR(255) NOT NULL,
    question    TEXT,
    label       VARCHAR(255),
    category    VARCHAR(100) DEFAULT 'General',
    hint        TEXT,
    data_type   VARCHAR(50) DEFAULT 'text',
    is_required BOOLEAN DEFAULT TRUE,
    UNIQUE (plan_id, key)
);

CREATE INDEX IF NOT EXISTS idx_iso_placeholder_dict_plan
ON dna_app.iso_placeholder_dictionary(plan_id);

COMMIT;
```

**Run it**:
```bash
docker exec -i dna-postgres psql -U dna_user -d dna < DNA/dashboard/migrations/008_iso_placeholder_dictionary.sql
```

---

### Step 2 — Update LLM Prompt in DB

The `iso_build` prompt is stored in `dna_app.ai_prompts` (key = `iso_build`).

**Changes to make to the prompt text**:

1. Remove the entire "FILLABLE_SECTIONS DEDUPLICATION RULE" section
2. Remove `fillable_sections` from the template JSON structure — templates only have `fixed_sections`
3. Add a top-level `placeholder_dictionary` array to the required output format

**New output format the LLM must produce**:
```json
{
  "summary": { ... },
  "placeholder_dictionary": [
    {
      "key": "organization_name",
      "question": "What is the full legal name of your organization?",
      "label": "Organization Name",
      "category": "Company Info",
      "hint": "As it appears on official documents",
      "data_type": "text",
      "is_required": true
    }
  ],
  "templates": [
    {
      "name": "ISMS 01 - Information Security Policy",
      "covered_clauses": ["5.2"],
      "covered_controls": ["A.5.1"],
      "fixed_sections": [
        {
          "id": "section_1",
          "title": "Policy Statement",
          "content": "{{organization_name}} is committed to..."
        }
      ]
    }
  ]
}
```

**Key LLM instructions to add**:
- Scan ALL templates for `{{keys}}` and define EVERY key in `placeholder_dictionary` exactly once
- Normalize semantically equivalent keys to one canonical key (e.g. `company`/`company_name`/`organization_name` → `organization_name`)
- Use `lowercase_underscore` format for all keys
- Templates contain ONLY `fixed_sections` — no `fillable_sections` array

**Run the update**:
```bash
docker exec -i dna-postgres psql -U dna_user -d dna
```
Then:
```sql
UPDATE dna_app.ai_prompts
SET prompt_text = '<new prompt text here>'
WHERE prompt_key = 'iso_build';
```

To read the current prompt first:
```sql
SELECT prompt_text FROM dna_app.ai_prompts WHERE prompt_key = 'iso_build';
```

---

### Step 3 — Update AI Service: Parse `placeholder_dictionary` from LLM Response

**File**: `DNA/ai-service/stream_consumer.py`

In `_handle_iso_build_task()`, the LLM result is returned by `iso_agent.build_from_pdf()` and
currently only `summary` and `templates` are extracted. Add extraction of `placeholder_dictionary`.

**File**: `DNA/ai-service/agents/iso_builder.py`

In `build_from_pdf()`, the return dict currently is:
```python
return {
    "summary": data.get("summary", {}),
    "templates": data.get("templates", []),
    ...
}
```

Add `placeholder_dictionary` to the return:
```python
return {
    "summary": data.get("summary", {}),
    "placeholder_dictionary": data.get("placeholder_dictionary", []),
    "templates": data.get("templates", []),
    ...
}
```

**Back in `stream_consumer.py`**, in `_handle_iso_build_task()`, after inserting the `iso_standards`
row, save the dictionary:

```python
placeholder_dictionary = result.get('placeholder_dictionary', [])

# Save placeholder_dictionary to iso_standards
async with db_client._pool.acquire() as conn:
    await conn.execute(
        f"UPDATE {settings.DATABASE_APP_SCHEMA}.iso_standards "
        f"SET placeholder_dictionary = $1::JSONB WHERE id = $2",
        _json.dumps(placeholder_dictionary), iso_row['id']
    )
```

This happens right after the `iso_standards` INSERT (around line where `iso_standard_id` is set).

Also update the template INSERT loop — since templates no longer have `fillable_sections`, update
the stats calculation:
```python
# Before (old):
total_fillable = len(tmpl.get('fillable_sections', []))
semantic_tags = list({tag for s in tmpl.get('fillable_sections', []) for tag in s.get('semantic_tags', [])})

# After (new):
total_fillable = 0  # No longer per-template
semantic_tags = []  # Will be derived from placeholder_dictionary if needed
```

---

### Step 4 — Populate Dictionary When Customer Plan Is Created

**File**: `DNA/dashboard/backend/app/routes/iso_customers.py`

In `create_iso_customer()`, after the plan is inserted and `plan_id` is obtained (around line 260),
add a call to copy the dictionary from `iso_standards` into `iso_placeholder_dictionary`:

```python
# After: plan_id = plan_row['id']
# Add this block:
await conn.execute(f"""
    INSERT INTO {settings.DATABASE_APP_SCHEMA}.iso_placeholder_dictionary
        (plan_id, key, question, label, category, hint, data_type, is_required)
    SELECT $1,
           entry->>'key',
           entry->>'question',
           entry->>'label',
           COALESCE(entry->>'category', 'General'),
           entry->>'hint',
           COALESCE(entry->>'data_type', 'text'),
           COALESCE((entry->>'is_required')::boolean, true)
    FROM {settings.DATABASE_APP_SCHEMA}.iso_standards,
         jsonb_array_elements(placeholder_dictionary) AS entry
    WHERE id = $2
      AND jsonb_array_length(placeholder_dictionary) > 0
    ON CONFLICT (plan_id, key) DO NOTHING
""", plan_id, assignment.iso_standard_id)
```

This runs inside the existing `async with pool.acquire() as conn:` block, using the same `conn`.

**Note**: There is also a separate `iso_plans.py` route that may handle plan creation independently.
Check `DNA/dashboard/backend/app/routes/iso_plans.py` — if it has a plan creation endpoint, add the
same dictionary copy logic there too.

---

### Step 5 — Simplify `seed_placeholders`

**File**: `DNA/dashboard/backend/app/services/task_generator_service.py`

Replace the entire `seed_placeholders` function. The current implementation has ~60 lines of
cross-template fallback logic. Replace with:

```python
async def seed_placeholders(conn, customer_id: int, plan_id: UUID, template: Dict[str, Any]) -> int:
    import re
    structure = _get_structure(template)
    template_id = template['id']

    # Find all {{keys}} used in this template's text
    all_text = json.dumps(structure)
    used_keys = {m.group(1).strip() for m in re.finditer(r'\{\{([^}]+)\}\}', all_text)}
    if not used_keys:
        return 0

    # Lookup from plan's placeholder dictionary
    dict_rows = await conn.fetch(f"""
        SELECT key, question, label, category, hint, data_type, is_required
        FROM {settings.DATABASE_APP_SCHEMA}.iso_placeholder_dictionary
        WHERE plan_id = $1 AND key = ANY($2)
    """, plan_id, list(used_keys))
    dict_map = {r['key']: r for r in dict_rows}

    seeded = 0
    for key in used_keys:
        d = dict_map.get(key) or {}
        question = d.get('question') or key.replace('_', ' ').title()
        display_label = d.get('label') or key.replace('_', ' ').title()
        category = d.get('category') or 'General'
        hint = d.get('hint')
        data_type = d.get('data_type') or 'text'
        is_required = d.get('is_required') if d.get('is_required') is not None else True

        existing_answer = await conn.fetchrow(
            f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_profile_data "
            f"WHERE customer_id = $1 AND field_key = $2",
            customer_id, key
        )
        initial_status = 'collected' if existing_answer else 'pending'
        profile_data_id = existing_answer['id'] if existing_answer else None

        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                (customer_id, plan_id, placeholder_key, display_label, question,
                 category, hint, data_type, is_required, status,
                 profile_data_id, template_ids)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, ARRAY[$12::uuid])
            ON CONFLICT (customer_id, plan_id, placeholder_key) DO UPDATE SET
                template_ids = array_append(
                    COALESCE(customer_placeholders.template_ids, ARRAY[]::uuid[]),
                    $12::uuid
                ),
                question    = COALESCE(NULLIF(customer_placeholders.question, ''), EXCLUDED.question),
                category    = COALESCE(NULLIF(customer_placeholders.category, 'General'), EXCLUDED.category),
                profile_data_id = COALESCE(customer_placeholders.profile_data_id, EXCLUDED.profile_data_id),
                status = CASE WHEN customer_placeholders.status = 'collected' THEN 'collected' ELSE EXCLUDED.status END
        """, customer_id, plan_id, key, display_label, question,
            category, hint, data_type, is_required,
            initial_status, profile_data_id, template_id)
        seeded += 1

    return seeded
```

Note: `example_value` and `semantic_tags` columns are removed from the INSERT since the new
dictionary doesn't carry them. If needed, they can be added back to `iso_placeholder_dictionary`.

---

### Step 6 — Backward Compatibility: Handle Plans Without Dictionary

Some existing customer plans were created before this change and will have no rows in
`iso_placeholder_dictionary`. The simplified `seed_placeholders` will still work — it just won't
find any dict entries and will fall back to `key.replace('_', ' ').title()` for labels/questions.

For existing ISO standards that were built before this change, `placeholder_dictionary` will be `[]`.
No action needed — the old cross-template logic can be kept as a fallback branch:

```python
# In seed_placeholders, after dict lookup:
if not dict_map:
    # Fallback: old cross-template lookup for pre-migration standards
    # (keep existing fallback code here temporarily)
    pass
```

Remove this fallback once all ISO standards have been rebuilt with the new prompt.

---

### Step 7 — Cleanup (after validation)

- Remove `fillable_sections` parsing from `generate_tasks_for_document()` in `task_generator_service.py`
  (or keep it — it only generates tasks for `is_mandatory`/`requires_evidence` sections, which won't
  exist in new templates anyway)
- Remove the cross-template fallback block from `seed_placeholders` once confirmed working
- Update `catalog_templates.py` `_sync_fillable_from_text()` helper if it's still being called

---

## Files to Modify Summary

| File | Change |
|------|--------|
| `DNA/dashboard/migrations/008_iso_placeholder_dictionary.sql` | **CREATE** — new migration |
| `dna_app.ai_prompts` (DB row, key=`iso_build`) | **UPDATE** — remove dedup rule, add `placeholder_dictionary` to output format |
| `DNA/ai-service/agents/iso_builder.py` | **EDIT** — add `placeholder_dictionary` to return dict |
| `DNA/ai-service/stream_consumer.py` | **EDIT** — save `placeholder_dictionary` to `iso_standards` after build |
| `DNA/dashboard/backend/app/routes/iso_customers.py` | **EDIT** — copy dict to `iso_placeholder_dictionary` on plan creation |
| `DNA/dashboard/backend/app/routes/iso_plans.py` | **CHECK + EDIT** — same dict copy if plan creation exists here |
| `DNA/dashboard/backend/app/services/task_generator_service.py` | **EDIT** — replace `seed_placeholders` with simplified version |

---

## Out of Scope (for now)
- Reference-doc-generated templates (handled separately once regular flow is stable)
- `iso_build_formal` prompt variant (apply same changes after `iso_build` is validated)
- Frontend changes — Interview tab already reads from `customer_placeholders`, no change needed
