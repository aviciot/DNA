# LLM Usage Tracking — Analysis & Plan

## Current State

### Tables involved

| Table | What it stores | Has customer_id? |
|---|---|---|
| `ai_tasks` | One row per background AI job (parse, generate, build) | ✅ just added |
| `ai_usage_log` | One row per LLM API call within a job (child of ai_tasks) | ✅ just added |
| `portal_activity_log` | Portal events (currently only login) | ✅ yes |
| `llm_providers` | Provider config + cost_per_1k_input/output rates | — |

### What is tracked today ✅
- Background AI jobs: tokens + cost in `ai_tasks` + `ai_usage_log`
- Customer login events in `portal_activity_log`

### What is NOT tracked ❌
- **Portal chat messages** — no history, no tokens, no cost saved
- **Dashboard admin chat** — same, nothing saved
- **Per-customer chat cost limits** — no concept exists

---

## Plan

---

### 1. AI Provider Tab — Global Usage Dashboard

**Where:** `dashboard → Configuration → AI Providers` (add a "Usage" tab to `LLMProvidersConfig.tsx`)

**What to show:**
- Total tokens + cost per provider (all time + last 30 days)
- Breakdown by task type (iso_build, document_generate, template_parse, chat)
- Grand total across all providers

**Data source:** `ai_usage_log` grouped by `provider` — already has everything needed.

**What needs building:**
- Backend: `GET /api/v1/admin/llm-providers/usage?days=30`
  ```sql
  SELECT provider, model,
         SUM(tokens_input) AS tokens_in,
         SUM(tokens_output) AS tokens_out,
         SUM(cost_usd) AS total_cost,
         COUNT(*) AS call_count
  FROM dna_app.ai_usage_log
  WHERE started_at > NOW() - INTERVAL '30 days'
  GROUP BY provider, model
  ```
- Frontend: Add "Usage" tab in `LLMProvidersConfig.tsx` with a simple table + totals row

**Effort:** Small — data already exists, just needs a query + UI tab.

---

### 2. Customer Portal — Total LLM Usage

**Where:** `dashboard → Configuration → AI Providers → Usage` (same tab, portal section)

**Problem:** Portal chat calls LLM but **never logs anything**. Need to add logging to `customer-portal/backend/app/routes/chat.py`.

**What needs building:**

#### Step 1 — Log chat usage to `ai_usage_log`
After each LLM response in `_stream_final()`, insert a row:
```python
await conn.execute("""
    INSERT INTO dna_app.ai_usage_log
    (operation_type, provider, model, tokens_input, tokens_output,
     cost_usd, status, customer_id, started_at, completed_at)
    VALUES ('portal_chat', $1, $2, $3, $4, $5, 'success', $6, $7, NOW())
""", provider, model, tokens_in, tokens_out, cost, customer_id, started_at)
```

#### Step 2 — Calculate cost
Use `llm_providers.cost_per_1k_input` and `cost_per_1k_output` already in DB.

#### Step 3 — Show in UI
Same usage tab, add a "Portal Chat" row per provider.

**Effort:** Medium — need to capture token counts from each LLM SDK response.

---

### 3. Customer Workspace — Per-Customer Usage + Limits

**Where:** `dashboard → Customers → [Customer] workspace`

**What to show:**
- Total tokens + cost this month for this customer
- Breakdown: background AI jobs vs portal chat
- Usage limit setting (monthly $ cap)

**What needs building:**

#### Step 1 — DB: add limit column to customers
```sql
ALTER TABLE dna_app.customers
    ADD COLUMN monthly_llm_budget_usd NUMERIC(10,2) DEFAULT NULL;
-- NULL = no limit
```

#### Step 2 — Backend: usage query per customer
```sql
SELECT
    SUM(cost_usd) AS total_cost,
    SUM(tokens_input + tokens_output) AS total_tokens,
    operation_type
FROM dna_app.ai_usage_log
WHERE customer_id = $1
  AND started_at >= date_trunc('month', NOW())
GROUP BY operation_type
```

#### Step 3 — Backend: enforce limit in portal chat
Before calling LLM, check:
```python
spent = await get_customer_monthly_spend(customer_id)
if budget and spent >= budget:
    raise LimitExceededError
```

#### Step 4 — Frontend: add usage panel to customer workspace
- Show current month spend vs budget (progress bar)
- Edit budget inline
- Table: date, operation, provider, tokens, cost

**Effort:** Medium-large — requires DB migration, backend enforcement, and frontend panel.

---

## Implementation Order

1. **AI Provider usage tab** — quickest win, data already exists
2. **Portal chat logging** — enables all downstream customer tracking
3. **Customer workspace usage panel** — depends on #2
4. **Per-customer budget limits** — depends on #2 + #3
