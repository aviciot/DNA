# Help Me Answer — Implementation Plan

## Overview

Add a **"💡 Help me answer"** button to each pending task card in the customer portal.
Clicking it opens an inline expandable box below the card that streams an AI-generated
explanation of what the question is asking, why it matters for ISO compliance, and how
to answer it — using the actual template section text as context.

---

## Problem

The AI assistant in the chat widget has no access to the actual template document content.
It only sees `hint` and `example_value` from `customer_placeholders`, which are often empty.
The rich context (ISO clause text, section purpose, surrounding policy language) lives in
`templates.template_structure` JSONB and is never surfaced to the AI or the customer.

---

## Architecture

```
[QuestionList TaskCard]
  → click "Help me answer"
  → POST /portal/task-help { task_id }   (HTTP, not WebSocket)
  → portal backend: fetch template context from DB
  → call LLM with context, stream SSE response
  → HelpBox component renders streamed text inline
```

---

## Impacted Files

### New Files

| File | Purpose |
|------|---------|
| `customer_portal_mcp/server/tools/template_context.py` | New MCP tool `get_template_context` |
| `customer-portal/frontend/src/components/HelpBox.tsx` | Inline streaming AI explanation component |

### Modified Files

| File | Change |
|------|--------|
| `customer_portal_mcp/server/tools/__init__.py` | Import `template_context` module |
| `customer-portal/backend/app/routes/portal.py` | Add `POST /task-help` SSE endpoint |
| `customer-portal/backend/app/main.py` | No change needed (portal_router already mounted) |
| `customer-portal/frontend/src/components/QuestionList.tsx` | Add `HelpBox` + "Help me answer" button to `TaskCard` |

---

## Step 1 — MCP Tool: `get_template_context`

**File:** `customer_portal_mcp/server/tools/template_context.py`

Query path:
```
customer_tasks (task_id) 
  → template_id → templates.template_structure JSONB
  → customer_placeholders (placeholder_key, plan_id) → question, hint, example_value
```

The tool walks `template_structure.sections[]` and their `subsections[]` to find the
section whose `content` contains `{{placeholder_key}}`. Returns:

```json
{
  "placeholder_key": "crypto_algorithm",
  "question": "Which encryption algorithms does your organisation use?",
  "hint": "",
  "example_value": "",
  "iso_reference": "ISO 27001:2022 A.8.24",
  "section_title": "Cryptographic Procedures",
  "section_content": "The organisation shall use the following approved algorithms: {{crypto_algorithm}}...",
  "document_purpose": "<text of the first section with title matching 'purpose' or 'scope'>",
  "template_name": "ISMS 06 Cryptography"
}
```

If the placeholder is not found in any section, return the full first section as fallback context.

**Also modify:** `customer_portal_mcp/server/tools/__init__.py`
```python
from tools import template_context  # noqa: F401
```

---

## Step 2 — Backend Endpoint: `POST /portal/task-help`

**File:** `customer-portal/backend/app/routes/portal.py`

Add at the bottom of the file:

```python
from fastapi.responses import StreamingResponse

class HelpPayload(BaseModel):
    task_id: str

@router.post("/task-help")
async def task_help(payload: HelpPayload, session: dict = Depends(validate_token)):
    ...
```

Flow:
1. Call MCP tool `get_template_context(token, task_id)` via `fastmcp.Client`
2. Build a focused system prompt:
   ```
   You are an ISO compliance assistant. Explain what this question is asking and 
   how to answer it. Be concise (3-5 sentences). No bullet lists. Plain language.
   ```
3. Build user message from the context dict (section text, ISO ref, question, hint)
4. Stream LLM response as `text/event-stream` SSE:
   ```
   data: <token>\n\n
   data: [DONE]\n\n
   ```
5. Use same `_get_llm_config()` helper already in `chat.py` — import it or move to `app/llm.py`

**Note on `_get_llm_config`:** Currently defined in `chat.py`. Either:
- Import it: `from app.routes.chat import _get_llm_config` (simplest, no refactor)
- Or extract to `app/llm.py` if reuse grows (not needed now)

---

## Step 3 — Frontend Component: `HelpBox`

**File:** `customer-portal/frontend/src/components/HelpBox.tsx`

Props:
```typescript
interface HelpBoxProps {
  taskId: string;
  onClose: () => void;
}
```

Behaviour:
- On mount: `fetch("/api/portal/task-help", { method: "POST", body: { task_id } })`
- Read SSE stream via `ReadableStream` / `TextDecoder`
- Parse `data: <token>` lines, accumulate into `text` state
- Render as `<p>` with a blinking cursor `|` while streaming
- Show a subtle "✕ Close" link at top-right
- Styled to match existing card surface (`var(--surface2)`, `var(--border)`)
- Animate open with `motion.div` (same pattern as existing `AnimatePresence` in `QuestionList`)

---

## Step 4 — Wire into `QuestionList.tsx`

**File:** `customer-portal/frontend/src/components/QuestionList.tsx`

Changes to `TaskCard`:
1. Add `showHelp` boolean state (default `false`)
2. Add `💡 Help me answer` button — only shown when `!isDone && expanded`
3. Render `<HelpBox taskId={q.id} onClose={() => setShowHelp(false)} />` below the textarea when `showHelp === true`
4. Import `HelpBox`

Button placement: below the textarea, left of "Save Answer" button.

```tsx
{!isDone && (
  <button onClick={() => setShowHelp(!showHelp)} ...>
    💡 Help me answer
  </button>
)}
{showHelp && <HelpBox taskId={q.id} onClose={() => setShowHelp(false)} />}
```

---

## Next.js API Route

**File:** `customer-portal/frontend/src/app/api/portal/task-help/route.ts`

Proxy POST to backend, pass through SSE stream. Same pattern as other `/api/portal/*` routes.

Check existing routes in `src/app/api/portal/` to confirm proxy pattern — likely:
```typescript
export async function POST(req: Request) {
  const body = await req.json();
  const res = await fetch(`${BACKEND_URL}/portal/task-help`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: ... },
    body: JSON.stringify(body),
  });
  return new Response(res.body, { headers: { "Content-Type": "text/event-stream" } });
}
```

---

## Data Flow Summary

```
TaskCard (QuestionList.tsx)
  showHelp=true
    → HelpBox.tsx
        → POST /api/portal/task-help (Next.js proxy)
            → POST /portal/task-help (FastAPI portal.py)
                → MCP get_template_context(token, task_id)
                    → DB: customer_tasks → templates.template_structure JSONB
                    → DB: customer_placeholders (question, hint)
                → _get_llm_config() [from chat.py]
                → LLM stream → SSE
            ← SSE tokens
        ← SSE tokens
      renders streamed text inline
```

---

## DB Query in `get_template_context`

```sql
SELECT 
    ct.placeholder_key,
    ct.template_id,
    t.name AS template_name,
    t.template_structure,
    cp.question,
    cp.hint,
    cp.example_value
FROM dna_app.customer_tasks ct
LEFT JOIN dna_app.templates t ON t.id = ct.template_id
LEFT JOIN dna_app.customer_placeholders cp 
    ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
WHERE ct.id = $1::uuid AND ct.customer_id = $2
```

Then in Python: walk `template_structure["sections"]` → find section containing
`{{placeholder_key}}` in `content` or any `subsections[].content`.

---

## Out of Scope (this iteration)

- Logging help requests to `ai_usage_log` (can add later per llm-usage-tracking-plan.md)
- Caching help responses
- "Was this helpful?" feedback
- Chat widget integration (help box is standalone)
