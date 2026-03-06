# Customer Portal MCP — Implementation Plan

## Name
`customer_portal_mcp` (renamed from `template_mcp`)

---

## Purpose
An MCP server that gives AI assistants (Claude, Cursor, etc.) full context about a customer's ISO compliance journey — their tasks, documents, progress, and template content — so the assistant can guide them conversationally, explain what each question means, and help them complete their certification.

---

## Security Model (Critical)

Every tool call requires a `token` parameter (the same portal email token from `email_collection_requests`).

Token validation flow:
1. Query `email_collection_requests` WHERE `token = $1 AND status != 'cancelled' AND expires_at > NOW()`
2. Returns `customer_id`, `plan_id` — these are the **only** IDs used for all subsequent queries
3. Every DB query is scoped with `AND customer_id = $customer_id` — no cross-customer data leakage possible
4. Token validated on **every tool call**, not cached in memory

DB user: `portal_user` — same restricted user as the portal. No new grants needed beyond migration 005.

---

## DB Table Map

| Table | Used For |
|---|---|
| `email_collection_requests` | Token → customer_id, plan_id resolution |
| `customers` | Customer name, contact info |
| `customer_iso_plans` | Plan name, target date, status |
| `iso_standards` | ISO code, name, description, requirements_summary |
| `customer_tasks` | Tasks list, status, priority, placeholder_key, answer |
| `customer_placeholders` | Question text, hint, example_value, category, semantic_tags |
| `customer_documents` | Document list, completion %, status per document |
| `templates` | Template name, description, covered_clauses, covered_controls |
| `customer_profile_data` | Already-collected answers (field_key → field_value) |
| `customer_configuration` | Per-customer config: language, tone, max_tokens, max_context_messages |
| `ai_prompts` | System prompt text loaded from DB by prompt_key |
| `llm_providers` | Which LLM to use (is_default_chat), model, max_tokens, cost rates |
| `ai_usage_log` | LLM usage tracking per customer per chat turn |

**Key join for task context** (what document/clause is this question for):
```
customer_tasks
  → template_id      → templates          (name, covered_clauses, covered_controls)
  → placeholder_key  → customer_placeholders (question, hint, example_value, category)
  → document_id      → customer_documents  (document_name, completion_percentage)
```

---

## Configuration in DB (Requirement #8)

All runtime config lives in existing tables — no new tables needed.

### `customer_configuration` rows (`config_type = 'mcp_chat'`)

| config_key | default value | Description |
|---|---|---|
| `language` | `"en"` | Chat response language (`"en"` or `"he"`) |
| `chat_tone` | `"friendly"` | Assistant tone |
| `max_context_messages` | `20` | Conversation history window |
| `max_tokens` | `8192` | LLM response token limit |

`customer_id = NULL` rows = global defaults. Customer-specific rows override them.

### `llm_providers` (existing)
- `is_default_chat = true` → which provider/model the MCP uses
- `max_tokens` → hard cap per provider
- `cost_per_1k_input/output` → used for usage cost calculation

### `ai_prompts` (existing)
- `prompt_key = 'portal_mcp_system'` → system prompt template with `{customer_name}`, `{iso_name}`, `{language}`, `{pending_count}` placeholders
- Loaded fresh from DB per session — update prompt without redeployment

---

## File Structure

```
customer_portal_mcp/
├── server/
│   ├── config/
│   │   ├── settings.yaml          # mcp.name, server.port, database section
│   │   └── settings.dev.yaml
│   ├── db/
│   │   ├── __init__.py
│   │   └── connector.py           # real asyncpg pool, singleton
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── auth.py                # validate_token() shared helper (not a tool)
│   │   ├── progress.py            # tool: get_progress
│   │   ├── tasks.py               # tool: get_tasks
│   │   ├── task_detail.py         # tool: get_task_detail (rich context)
│   │   ├── answer.py              # tool: submit_answer
│   │   ├── documents.py           # tool: get_documents
│   │   └── usage.py               # tool: log_llm_usage
│   ├── resources/
│   │   ├── __init__.py
│   │   └── portal_context.py      # resource: context://customer/{token}
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── portal_assistant.py    # prompt: portal_assistant (loaded from ai_prompts table)
│   ├── utils/                     # inherited from template unchanged
│   ├── mcp_app.py                 # unchanged
│   ├── server.py                  # + DB lifespan connect/disconnect
│   ├── config.py                  # unchanged
│   ├── auth_middleware.py         # unchanged
│   └── requirements.txt
├── .env
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── PLAN.md
```

---

## Tools

### `get_progress` — `tools/progress.py`
**Input:** `token: str`, `plan_id: str | None`
**Query:** `customer_tasks` COUNT by status + `customer_iso_plans` JOIN `iso_standards`
**Returns:** total, completed, pending, evidence_pending, percentage, target_date, plan_name, iso_name
**Security:** token → customer_id, all counts WHERE customer_id = $cid AND plan_id = $pid

---

### `get_tasks` — `tools/tasks.py`
**Input:** `token: str`, `plan_id: str | None`, `status_filter: str | None`, `priority_filter: str | None`
**Query:**
```sql
SELECT ct.id, ct.title, ct.description, ct.status, ct.priority,
       ct.placeholder_key, ct.due_date, ct.requires_evidence, ct.answer,
       cp.question, cp.hint, cp.category
FROM customer_tasks ct
LEFT JOIN customer_placeholders cp
  ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
WHERE ct.customer_id = $cid AND ct.plan_id = $pid
  AND ct.is_ignored = false AND ct.status != 'cancelled'
ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
```
**Returns:** task list with question text and hint already joined in

---

### `get_task_detail` — `tools/task_detail.py`
**Input:** `token: str`, `task_id: str`
**Query:**
```sql
SELECT ct.*,
       cp.question, cp.hint, cp.example_value, cp.category, cp.semantic_tags,
       t.name AS template_name, t.description AS template_description,
       t.covered_clauses, t.covered_controls,
       cd.document_name, cd.completion_percentage
FROM customer_tasks ct
LEFT JOIN customer_placeholders cp
  ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
LEFT JOIN templates t ON t.id = ct.template_id
LEFT JOIN customer_documents cd ON cd.id = ct.document_id
WHERE ct.id = $task_id AND ct.customer_id = $cid  -- $cid from token
```
**Returns:** full task context — which document, which ISO clause, question text, hint, example answer
**Purpose:** The "explain this question" tool. Gives LLM everything to guide the customer on a specific task.

---

### `submit_answer` — `tools/answer.py`
**Input:** `token: str`, `task_id: str`, `placeholder_key: str`, `value: str`
**Writes:**
- UPDATE `customer_tasks` SET answer, status='answered', answered_via='portal_mcp'
- UPSERT `customer_profile_data` (field_key → value)
**Security:** verify `task.customer_id = token.customer_id` before any write
**Returns:** `{ok: true}`

---

### `get_documents` — `tools/documents.py`
**Input:** `token: str`, `plan_id: str | None`
**Query:** `customer_documents` JOIN `templates` WHERE customer_id = $cid AND plan_id = $pid
**Returns:** document list with name, status, completion_percentage, template_name, due_date
**Purpose:** "Which documents do I need to complete and how far along am I?"

---

### `log_llm_usage` — `tools/usage.py`
**Input:** `token: str`, `provider: str`, `model: str`, `tokens_input: int`, `tokens_output: int`, `cost_usd: float`, `operation: str`
**Writes:** INSERT into `ai_usage_log` with `related_entity_type='portal_mcp'`, `related_entity_id=customer_id`
**Purpose:** Per-customer LLM usage tracking (requirement #6). Reuses existing table — visible in existing dashboard.

---

## Resources

### `context://customer/{token}` — `resources/portal_context.py`
Returns a full JSON snapshot of the customer's current state in one call:
- Customer name, ISO plan, language preference (from `customer_configuration`)
- Progress summary (%, counts by status)
- Pending tasks grouped by priority (top 20, with question + hint)
- Documents list with completion %
- Already-collected profile data (field_key → value) — LLM knows what's already answered

**Purpose:** LLM reads this at session start for full context. Enables long-context conversations without re-querying per message (requirement #7).
**Security:** token in URI → validated → all data scoped to that customer_id only

---

## Prompts

### `portal_assistant` — `prompts/portal_assistant.py`
**Input:** `token: str`

1. Fetches system prompt text from `ai_prompts` WHERE `prompt_key = 'portal_mcp_system'`
2. Fetches customer name, ISO plan name, pending count from DB
3. Fetches language from `customer_configuration` (customer-specific → fallback to global default)
4. Interpolates all placeholders and returns the rendered prompt

**Enforced by the prompt (configurable in DB):**
- Always respond in `{language}` (Hebrew or English)
- Only discuss this customer's tasks, documents, and ISO compliance
- Never invent information — only use data from tool responses
- Never discuss other customers or unrelated topics
- If asked off-topic: "I can only help with your {iso_name} compliance tasks"
- Be friendly, encouraging, explain WHY each question matters

---

## DB Connector — `db/connector.py`

```python
class PortalDBConnector:
    async def connect(self)       # asyncpg.create_pool, min=2, max=10
    async def disconnect(self)    # pool.close()
    async def fetchrow(self, query, *args) -> dict | None
    async def fetch(self, query, *args) -> list[dict]
    async def execute(self, query, *args)
    async def health_check(self) -> bool  # SELECT 1

db = PortalDBConnector(...)  # singleton
```

Initialized in `server.py` lifespan — `await db.connect()` on startup, `await db.disconnect()` on shutdown.

Config via `settings.yaml`:
```yaml
database:
  host: ${PORTAL_DB_HOST}
  port: ${PORTAL_DB_PORT}
  name: ${PORTAL_DB_NAME}
  user: ${PORTAL_DB_USER}
  password: ${PORTAL_DB_PASSWORD}
  schema: dna_app
  pool_size: 10
```

---

## Migration: `005_portal_mcp.sql`

No new tables. Only seeds data + grants:

```sql
-- System prompt
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, model, max_tokens, description)
VALUES (
  'portal_mcp_system',
  'You are a friendly ISO compliance assistant for {customer_name}, helping them complete
their {iso_name} certification.

RULES:
- Always respond in {language}
- Only discuss tasks, documents, and questions related to this customer''s compliance plan
- Never invent information — only use data returned by tools
- Never discuss other customers or unrelated topics
- Current status: {pending_count} tasks pending
- Be encouraging and explain WHY each question matters for ISO compliance
- If asked off-topic: respond only in {language}: "I can only help with your {iso_name} compliance tasks"',
  'gemini-2.5-flash', 8192, 'Portal MCP chat system prompt'
) ON CONFLICT (prompt_key) DO NOTHING;

-- Global MCP chat config defaults (customer_id = NULL)
INSERT INTO dna_app.customer_configuration
  (customer_id, config_type, config_key, config_value, is_default)
VALUES
  (NULL, 'mcp_chat', 'language',             '"en"',    true),
  (NULL, 'mcp_chat', 'chat_tone',            '"friendly"', true),
  (NULL, 'mcp_chat', 'max_context_messages', '20',      true),
  (NULL, 'mcp_chat', 'max_tokens',           '8192',    true)
ON CONFLICT (customer_id, config_type, config_key) DO NOTHING;

-- Grants for portal_user
GRANT SELECT ON dna_app.ai_prompts TO portal_user;
GRANT SELECT ON dna_app.customer_configuration TO portal_user;
GRANT SELECT ON dna_app.templates TO portal_user;
GRANT SELECT ON dna_app.customer_documents TO portal_user;
GRANT SELECT ON dna_app.llm_providers TO portal_user;
GRANT INSERT ON dna_app.ai_usage_log TO portal_user;
```

---

## `.env`

```env
PORTAL_DB_HOST=dna-postgres
PORTAL_DB_PORT=5432
PORTAL_DB_NAME=dna
PORTAL_DB_USER=portal_user
PORTAL_DB_PASSWORD=portal_user
MCP_PORT=4020
AUTH_ENABLED=false
AUTO_DISCOVER=true
```

---

## Long Context & Configurability (Requirements #7 & #8)

- `max_tokens` per customer from `customer_configuration` — default 8192, up to provider limit
- `max_context_messages` controls conversation history window passed to LLM
- `portal_context` resource gives full snapshot upfront — no repeated tool calls needed
- LLM provider selected from `llm_providers WHERE is_default_chat = true` — change in DB, no redeploy
- System prompt updated in `ai_prompts` table — no redeploy

---

## Language Support (Requirement #5)

- Language stored in `customer_configuration` (config_type=`mcp_chat`, config_key=`language`)
- `portal_assistant` prompt fetches it and injects into system prompt
- System prompt instructs LLM: "Always respond in {language}"
- Customer can say "ענה בעברית" or "answer in English" to override mid-session
- LLM handles translation natively — no separate translation layer

---

## Scope Enforcement (Requirement #5 — no hallucination, no off-topic)

Three layers:
1. **System prompt** (from DB): explicit rules — only use tool data, never invent, redirect off-topic
2. **Token-scoped queries**: physically impossible to retrieve another customer's data
3. **No general knowledge tools**: MCP exposes zero web search or general Q&A tools — only DB-backed tools

---

## Implementation Order

1. Rename `template_mcp` → `customer_portal_mcp` (folder rename)
2. `db/connector.py` — real asyncpg pool
3. `config/settings.yaml` — add database section
4. `server.py` — add DB lifespan
5. `tools/auth.py` — `validate_token()` helper
6. `tools/progress.py` + `tools/tasks.py`
7. `tools/task_detail.py` — most important tool
8. `tools/answer.py` + `tools/documents.py` + `tools/usage.py`
9. `resources/portal_context.py`
10. `prompts/portal_assistant.py`
11. `db/migrations/005_portal_mcp.sql`
12. `.env` + `docker-compose.yml`

---

## What We Are NOT Building

- No new auth system — reuses portal token
- No new DB tables — reuses existing schema entirely
- No frontend — pure MCP server
- No file upload via MCP — read + answer text only
- No admin tools — read-only except `submit_answer` and `log_llm_usage`
