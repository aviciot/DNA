# Help Me Answer — How It Works

## Flow

Customer clicks **"Help me answer"** on a task card in the portal.

```
TaskCard (QuestionList.tsx)
  → HelpBox.tsx mounts
    → POST /api/portal/task-help  (Next.js proxy)
      → POST /portal/task-help    (portal-backend FastAPI)
        → MCP: get_template_context(token, task_id)
            → DB query (see below)
            → walks template_structure JSONB
        → LLM with focused system prompt
        → SSE stream of tokens
      ← streamed tokens
    ← rendered inline below the textarea
```

---

## What Context the LLM Receives

The MCP tool `get_template_context` runs this DB query:

```sql
SELECT ct.placeholder_key, ct.template_id,
       t.name AS template_name, t.template_structure,
       cp.question, cp.hint, cp.example_value, cp.iso_reference
FROM customer_tasks ct
LEFT JOIN templates t ON t.id = ct.template_id
LEFT JOIN customer_placeholders cp
    ON cp.placeholder_key = ct.placeholder_key AND cp.plan_id = ct.plan_id
WHERE ct.id = $task_id AND ct.customer_id = $customer_id
```

Then it walks `template_structure.sections[]` (and `subsections[]`) to find
the section whose `content` field contains `{{placeholder_key}}`.

The LLM receives:
| Field | Source |
|---|---|
| `template_name` | e.g. "ISMS 06 Cryptography for Cloud Services" |
| `iso_reference` | e.g. "ISO 27017:2015 A.10.1" (from `customer_placeholders`) |
| `section_title` | e.g. "Cryptographic Procedures" |
| `section_content` | The surrounding policy text (up to 1000 chars) |
| `document_purpose` | First Purpose/Scope section of the document |
| `question` | The compliance question text |
| `hint` | Guidance note (often empty) |
| `example_value` | Example answer (often empty) |

The system prompt instructs the LLM: explain what is being asked, why it
matters for ISO compliance, and what a good answer looks like — in 3-5
sentences, plain language.

---

## The Multiple-Documents Question

`organization_name` (and similar universal placeholders) appears in many
templates. The current implementation only fetches context from **one
document** — the template linked to the specific task (`customer_tasks.template_id`).

**Does it need to go through all documents?** No — and here's why:

- The compliance *question* is always the same regardless of which document
  uses the placeholder. "What is your organisation's legal name?" is the same
  whether it appears in ISMS 01, ISMS 06, or ISMS 09.
- The surrounding section text adds ISO clause context but doesn't change the
  fundamental explanation.
- Sending 5 document sections for the same placeholder would waste tokens,
  slow the response, and likely confuse the explanation ("This appears in
  ISMS 01 as... but in ISMS 06 as...").

**Verdict:** One document is sufficient. The value is in the ISO clause
reference and section context, not in listing every document that uses the
placeholder.

The only case where multi-document context would add value is if the
placeholder has *different* meanings in different document types — which
doesn't happen in ISO compliance templates where `organization_name` always
means the same thing.

---

## Language Detection (Hebrew / Non-English Templates)

Currently the language is set in **Admin → Configuration → Customer Portal →
Help Me Answer → Language**. This is a global setting — not per-customer or
per-template.

**Better approach (not yet implemented):** Auto-detect from the template
content itself:

```python
# In get_template_context or task_help endpoint
question_text = ctx.get("question") or ctx.get("section_content") or ""
# Simple heuristic: check for Hebrew Unicode range (U+0590–U+05FF)
is_hebrew = any('\u0590' <= c <= '\u05FF' for c in question_text)
lang_instruction = "Respond in Hebrew." if is_hebrew else ""
```

This is more reliable than a global setting because:
- Some customers have Hebrew templates, others English — same portal instance
- The template itself is the source of truth for language
- Zero configuration needed

**Recommendation:** Replace the static language config with this auto-detect.
The admin language setting can remain as a fallback for ambiguous cases.
