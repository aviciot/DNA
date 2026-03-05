# Email Automation Service — Complete Guide

---

## What Is This?

The Email Automation Service lets DNA **automatically collect compliance data from customers via email**.

Instead of someone manually calling or chasing customers for information, the system:
1. **Sends** a branded, formatted email to the customer listing all their pending compliance questions
2. **Reads** the customer's reply (with IMAP — connects to your inbox like a mail client)
3. **Uses AI** to extract the answers from the email text and any attached documents
4. **Writes the answers back** into the DNA database — automatically updating task statuses

It both **sends** and **reads** email. Think of it as a two-way automated email assistant for compliance data collection.

---

## Is This the Same as the AI Worker (dna-ai-service)?

**No. It is a completely separate container: `dna-automation-service`.**

| | dna-ai-service | dna-automation-service |
|---|---|---|
| Purpose | ISO template generation (long builds) | Email send/receive/extract |
| Redis stream | `iso:build`, `doc:generate`, etc. | `automation:send`, `automation:extract` |
| AI role | Generates ISO documents | Extracts answers from email replies |
| Long-running jobs? | Yes (ISO build takes minutes) | No (quick email operations) |

They are kept separate deliberately — an ISO build takes 10–45 minutes and would block email processing if they shared a worker.

---

## The New AI Agent

A brand-new agent was created at **`automation-service/agents/email_extract_agent.py`**.

This agent is **not** the same as the ISO builder agent in `ai-service/agents/iso_builder.py`.

**What the Email Extract Agent does:**
- Receives the text body of a customer's email reply
- Receives any parsed text from attachments (PDF content, Word document text, Excel cells, images)
- Knows which questions were asked in the campaign email (loaded from DB)
- Calls the configured LLM (Claude / Gemini / Groq) with a structured prompt
- Returns a JSON object like this:

```json
{
  "answers": [
    {
      "placeholder_key": "company_name",
      "value": "Acme Corp Ltd",
      "confidence": 0.97,
      "reasoning": "Customer stated 'our company name is Acme Corp Ltd' in paragraph 1"
    }
  ],
  "evidence_matches": [
    {
      "task_id": "uuid-of-evidence-task",
      "filename": "ISO_27001_certificate.pdf",
      "confidence": 0.85,
      "reasoning": "Filename and content matches the requested ISO certificate"
    }
  ],
  "follow_up_keys": ["missing_field_1"],
  "notes": "Customer also mentioned they are renewing their certificate in Q2"
}
```

**Supported LLM providers for extraction:**
- Claude (Anthropic) — also supports image vision for scanned documents
- Gemini (Google) — also supports image vision
- Groq — text only, no image vision

The provider and model are configurable per the extraction settings in the Admin panel.

---

## Architecture Overview

```
[Dashboard User]
      │
      │  clicks "Send Campaign"
      ▼
[dna-backend]
  POST /api/v1/automation/{customer_id}/send-collection
      │
      │  writes to Redis stream "automation:send"
      ▼
[dna-automation-service / stream_consumer.py]
      │
      │  _handle_send():
      │    1. Loads customer's pending tasks from DB
      │    2. Builds HTML email with all questions/evidence listed
      │    3. Sends via Gmail SMTP or SendGrid
      │    4. Saves campaign record to email_collection_requests table
      ▼
[Customer's inbox]
  Receives beautiful HTML email, replies with answers
      │
      ▼
[dna-automation-service / scheduler.py]
  IMAP poll runs every 60 seconds:
      │
      │  _poll_imap_job():
      │    1. Connects to Gmail via IMAP4_SSL
      │    2. Fetches all UNSEEN emails
      │    3. Extracts +collect_TOKEN from To: header
      │    4. Saves attachments to storage/customers/emails/{log_id}/
      │    5. Saves raw email to email_inbound_log table
      │    6. Writes to Redis stream "automation:extract"
      ▼
[dna-automation-service / stream_consumer.py]
      │
      │  _handle_extract():
      │    1. Parses attachments (PDF/Word/Excel/images)
      │    2. Calls AI extraction agent with email text + attachment content
      │    3. AI returns answers with confidence scores
      │    4. Saves results to email_extraction_items table
      │    5. Auto-applies high-confidence answers directly to DB
      │       OR queues for human review (depending on config)
      ▼
[Database updated — final state after trigger chain]
  - customer_profile_data:   field_value saved / overwritten
  - customer_tasks:          status='completed', answer='...', answered_via='email'
  - customer_placeholders:   status='collected'
  - email_inbound_log:       status='applied', extraction_result=<LLM JSON>
```

---

## Full Task Lifecycle — Step by Step

This section describes the complete lifecycle of a single task/question from pending to completed, including all DB state changes.

### Phase 1 — Campaign Created

| Table | State |
|---|---|
| `customer_tasks` | `status='pending'`, `answered_via=NULL`, `answer=NULL` |
| `customer_placeholders` | `status='pending'` |
| `customer_profile_data` | row may not exist yet |
| `email_collection_requests` | row created after send: `status='pending'`, `questions_snapshot=[{...}]` |
| `email_inbound_log` | no row yet |

### Phase 2 — Email Sent to Customer

The stream consumer builds the email from all `pending` tasks in the plan, sends it via Gmail SMTP or SendGrid, and creates an `email_collection_requests` row with a `token`. The `Reply-To` header is set to `yourname+collect_TOKEN@gmail.com`.

### Phase 3 — Customer Replies

The IMAP listener polls every N seconds. When it finds the reply:

| Table | State |
|---|---|
| `email_inbound_log` | row created: `status='received'`, `body_text='...'`, `extraction_result=NULL` |

The email is then pushed to the `automation:extract` Redis stream.

### Phase 4 — AI Extraction

`_handle_extract()` runs:

| Table | State |
|---|---|
| `email_inbound_log` | `status='processing'` |

The LLM analyzes the email body + attachment text and returns answers with confidence scores.

| Table | State |
|---|---|
| `email_inbound_log` | `status='extracted'`, `extraction_result={answers:[...], notes:'...'}` |
| `email_extraction_items` | rows created: `status='auto_applied'` (high confidence) OR `'pending'` (needs review) |

### Phase 5 — Answer Applied (apply_answer() function)

For each high-confidence answer, `apply_answer()` runs these 4 steps **in this exact order**:

**Step 1 — Upsert profile data:**
```sql
INSERT INTO customer_profile_data (customer_id, field_key, field_value, source, filled_via, filled_at)
VALUES ($1, $2, $3, 'email', 'email', NOW())
ON CONFLICT (customer_id, field_key) DO UPDATE SET
    field_value = EXCLUDED.field_value,
    source = 'email',
    filled_via = 'email',
    filled_at = NOW(),
    updated_at = NOW()
```

**Step 2 — Update task FIRST (before placeholder):**
```sql
UPDATE customer_tasks
SET answer      = $3,
    answered_via = COALESCE(answered_via, 'email'),
    answered_at  = COALESCE(answered_at, NOW()),
    updated_at   = NOW(),
    status = CASE
        WHEN status = 'pending' THEN 'answered'
        ELSE status          -- already answered/completed: just refresh answer, don't change status
    END
WHERE customer_id = $1 AND placeholder_key = $2
  AND status != 'cancelled'
```

**Step 3 — Update placeholder (triggers the DB trigger):**
```sql
UPDATE customer_placeholders
SET status = 'collected', updated_at = NOW()
WHERE customer_id = $1 AND placeholder_key = $2
  AND ($3::uuid IS NULL OR plan_id = $3)
```

> **Important:** This triggers `trg_placeholder_to_task` — a DB trigger that fires on every UPDATE to `customer_placeholders`. The trigger calls `sync_task_from_placeholder()` which sets `customer_tasks.status = 'completed'` when the placeholder becomes `'collected'`. Because the task already has `answered_via` and `answer` set (Step 2), the trigger sees them correctly.

**Step 4 — Mark extraction item as applied:**
```sql
UPDATE email_extraction_items
SET status = 'auto_applied', applied_at = NOW()
WHERE id = $1
```

### Phase 5 — Final DB State (after all 4 steps + trigger)

| Table | Column | Value |
|---|---|---|
| `customer_profile_data` | `field_value` | answer text |
| `customer_profile_data` | `source` / `filled_via` | `'email'` |
| `customer_tasks` | `status` | `'completed'` (set by trigger) |
| `customer_tasks` | `answer` | answer text |
| `customer_tasks` | `answered_via` | `'email'` |
| `customer_tasks` | `answered_at` | timestamp |
| `customer_placeholders` | `status` | `'collected'` |
| `email_inbound_log` | `status` | `'applied'` |
| `email_inbound_log` | `extraction_result` | full LLM JSON (preserved, never overwritten) |
| `email_extraction_items` | `status` | `'auto_applied'` |

### The Trigger Chain (Detailed)

```
apply_answer()
  │
  ├─ UPDATE customer_tasks SET status='answered', answer=... ← Step 2
  │
  └─ UPDATE customer_placeholders SET status='collected'     ← Step 3
        │
        ▼
    [PostgreSQL trigger: trg_placeholder_to_task fires]
        │
        └─ sync_task_from_placeholder()
              │
              └─ UPDATE customer_tasks SET status='completed'
                 WHERE customer_id=X AND placeholder_key=Y
```

So the final task status is always `'completed'` — not `'answered'`. The `'answered'` state is transient and exists only briefly (the time between Step 2 and when the trigger fires, which is microseconds in the same transaction).

---

## What the Task Automation Section Shows

In the task detail panel (Customer Workspace → Tasks → click a task), the "Automation" section displays:

| Field | Populated when | Source |
|---|---|---|
| **Email sent** | After campaign is created | `email_collection_requests.sent_at` |
| **Sent to** | After campaign is created | `email_collection_requests.sent_to[]` |
| **Campaign #** | Each send/follow-up | `email_collection_requests.campaign_number` |
| **Reply received** | After IMAP captures reply | `email_inbound_log.received_at` |
| **Extracted via** | After AI extraction | `answered_via = 'email'` |
| **Answer** | After apply_answer() | `customer_tasks.answer` |
| **Confidence** | After AI extraction | `email_extraction_items.confidence` |
| **AI Notes** | After AI extraction | `email_inbound_log.extraction_result.notes` |
| **Status** | Final state | `customer_tasks.status` = `'completed'` |

The **AI Notes** field shows free-text observations the LLM made about the customer's email (e.g., "Customer mentioned they are ISO 27001 certified since 2020"). This is the `notes` field in the LLM JSON response, stored in `email_inbound_log.extraction_result`.

---

## What Happens If a Customer Sends a Second Reply?

### Short answer: Yes, second replies are fully processed. Existing answers are overwritten with the latest value.

Here is exactly what happens when a customer sends another email with answers (whether re-answering the same questions or answering new ones):

### 1. The IMAP listener picks it up as a new email
Each IMAP email creates a new `email_inbound_log` row. The second reply is processed completely independently from the first.

### 2. Token matching works as long as the original thread is used
If the customer replies to the same email thread, the `+collect_TOKEN` is still in the headers and the system matches the correct campaign request. If they start a fresh email, the fallback sender-email match is used.

### 3. AI extracts answers from the new email
A fresh LLM call is made with the new email body + attachments. This can produce overlapping answers (same `placeholder_key` answered again) or new answers for questions not answered in the first reply.

### 4. `customer_profile_data` is always UPSERTED
```sql
ON CONFLICT (customer_id, field_key) DO UPDATE SET field_value = EXCLUDED.field_value
```
**The latest value always wins.** If the customer changes their answer (e.g., first said "120 employees", now says "130 employees"), the profile data is overwritten with "130 employees". There is no versioning — only the latest answer is kept.

### 5. Task `answer` field is refreshed
The task UPDATE in `apply_answer()` always writes the new `answer` value regardless of current status:
```sql
SET answer = $3,
    answered_via = COALESCE(answered_via, 'email'),  -- keeps first channel if already set
    status = CASE WHEN status = 'pending' THEN 'answered' ELSE status END
```
- If the task was `pending` → it moves to `answered` (then trigger sets it to `completed`)
- If the task was already `completed` → status stays `completed`, but `answer` is refreshed with the new value
- The original `answered_at` timestamp is preserved via `COALESCE`

### 6. A second `email_extraction_items` row is created
The second reply produces new extraction items with their own confidence scores, timestamps, and reasoning. The history is fully preserved for audit purposes.

### Summary Table

| What happens | Behavior |
|---|---|
| Profile data | **Overwritten** with new value |
| Task `answer` field | **Refreshed** with new value |
| Task `status` | Stays `'completed'` — NOT re-opened |
| Task `answered_via` | Stays at first channel (COALESCE preserves original) |
| Old extraction items | Preserved in DB (audit trail) |
| New extraction items | New rows created for second reply |
| Total replies handled | Unlimited — every reply is processed |

---

## What Tasks Does It Collect?

The system reads from `customer_tasks` — the same tasks you see in the customer workspace.

Specifically it queries:

```sql
SELECT * FROM customer_tasks
WHERE customer_id = ?
  AND plan_id = ?
  AND status IN ('pending', 'in_progress')
  AND (is_ignored = false OR is_ignored IS NULL)
ORDER BY priority DESC
```

It then splits tasks into two categories:

| Task type | How identified | Goes into email as |
|---|---|---|
| **Question task** | Has a `placeholder_key` (e.g., `company_name`) | Listed as Q1, Q2, Q3... in the Questions section |
| **Evidence task** | Has `requires_evidence = true` | Listed as FILE 1, FILE 2... in the Documents section |

If there are no pending tasks at all, the campaign is skipped (nothing to ask).

---

## How Does It Know Which Reply Belongs to Which Customer?

### Where outbound emails are sent

Each customer can have up to **4 email fields** filled in:

| Customer field | Typical use |
|---|---|
| `compliance_email` | Main compliance contact |
| `contact_email` | General contact |
| `document_email` | Document submissions |
| `email` | Primary / fallback |

The campaign email is sent to **all of them at once** (any that are not empty). So if a customer has both `compliance_email` and `contact_email` filled, both get the email.

### The `+token` identification trick

When you configure `yourname@gmail.com`, the system sets the email's `Reply-To:` header to:
```
yourname+collect_ABCDEF1234567890@gmail.com
```

The `+collect_TOKEN` part is a Gmail feature: Gmail delivers this to your **normal inbox** without any extra configuration. When the customer hits Reply, their reply automatically goes to this address.

The IMAP listener reads the `To:` header of the incoming email and extracts `ABCDEF1234567890` — this token maps to the exact customer and plan in the `email_collection_requests` table.

### Fallback: match by sender address

If the token is missing (customer forwarded the email, replied from a different thread, or the `+` was stripped by their mail client), the system falls back to matching the **sender's `From:` email address** against all 5 email fields in the `customers` table:
```
email, contact_email, compliance_email, document_email, contract_email
```

If neither match — the email is logged but skipped (no customer association).

---

## Confidence Thresholds — Auto vs. Review

The AI assigns a confidence score (0.0 to 1.0) to each extracted answer. The system has three configurable thresholds:

| Score | Meaning | What happens |
|---|---|---|
| `>= auto_apply_threshold` (default 0.85) | High confidence | Answer applied automatically, no human needed |
| `>= confidence_floor` (default 0.60) but below threshold | Medium confidence | Queued in the Review Queue for a human to accept/reject |
| `< confidence_floor` | Low confidence | Discarded entirely — not saved |

### Review Modes (configurable in Admin → Automation):

| Mode | Behavior |
|---|---|
| **Hybrid** *(default)* | High-confidence → auto, medium → queue, low → discard |
| **Human-first** | Everything goes to the review queue, nothing auto-applies |
| **Autonomous** | All answers above floor are applied automatically |

---

## Per-Customer Automation Config

Each customer can have their own automation overrides that take precedence over the global settings. This is useful when different customers need:
- Different recipient email addresses than what's on file
- A different contact name in the email greeting
- Email in Hebrew (or another language)
- Different follow-up timing (wait 5 days instead of 2 for slower customers)
- Automation completely disabled for one specific customer

### How to configure

In the **Customer Workspace → Automation tab**, click the gear icon (⚙) in the "Send Collection Campaign" card header.

### Available per-customer overrides

| Setting | Default (global) | Per-customer override |
|---|---|---|
| **Enabled** | Global `enabled` flag | Can disable automation just for this customer |
| **Contact name** | Customer's `name` field | Custom greeting name (e.g., "Compliance Team") |
| **Language** | English | Hebrew (RTL) — email sent in Hebrew with right-to-left layout |
| **Send to emails** | All 4 customer email fields | Specific list of addresses |
| **Max follow-ups** | Global `max_followups` | Override per customer (e.g., 5 for slow responders) |
| **Follow-up delay** | Global `followup_delay_days` | Override per customer (e.g., 7 days instead of 2) |
| **Notes** | — | Internal notes (not sent to customer) |

### How overrides flow through the system

When the dashboard sends a campaign, it reads the per-customer config and injects overrides into the Redis message:

```
Redis message "automation:send":
  customer_id:     "42"
  plan_id:         "uuid..."
  contact_name:    "Compliance Team"     ← per-customer override
  language:        "he"                   ← Hebrew
  send_to_override: '["boss@co.com"]'    ← specific override list
  is_followup:     "false"
  ...
```

The stream consumer reads these from the message and applies them when building and sending the email.

### Disabled customers in the follow-up scheduler

The daily follow-up job filters out disabled customers:
```sql
WHERE COALESCE(cac.enabled, TRUE) = TRUE
```
A customer with `enabled = false` never receives automated follow-up emails. They can still be manually triggered via "Send Collection Email".

### When paused: amber banner in the UI

If a customer's automation is disabled (`enabled = false`), an amber warning banner appears at the top of their Automation tab:
> **Automation paused for this customer** — Automatic follow-ups are disabled. You can still send manual campaigns.

---

## Scheduled Automation

The service runs three background jobs via APScheduler:

### 1. IMAP Poll (every 60 seconds, configurable)
Connects to your inbox and checks for new unseen emails. Processes each one and marks it as read.

**You can also trigger a poll manually** via API — useful while testing or if you just sent a test reply and don't want to wait 60 seconds:

```
POST /api/v1/automation/trigger-imap-poll
Authorization: Bearer <token>
```

This pushes a trigger message to the `automation:imap_trigger` Redis stream, and the automation service picks it up and runs one immediate IMAP poll cycle.

### 2. Daily Follow-up (every day at 09:00)
Finds campaigns that:
- Are still in `pending` status (customer hasn't fully replied to everything)
- Were sent more than N days ago (configurable, default 2 days; overridable per customer)
- Have not yet hit the max follow-ups limit (configurable, default 3; overridable per customer)
- Belong to a customer that has `enabled = true` (or no override row)

**Important: the follow-up email only contains questions that are STILL unanswered.**
It does NOT blindly re-send the original email. It calls `get_pending_tasks_for_plan()` fresh from the database — so if the customer already answered 5 out of 8 questions (either via email or via the dashboard), the follow-up only lists the remaining 3 unanswered ones.

The email is sent with a yellow warning banner: _"Follow-up #2 — We sent a similar request a few days ago and still have 3 items awaiting your response."_

This means follow-ups get shorter and shorter as more questions get answered, until there's nothing left to ask — at which point the job skips that customer entirely.

### 3. Expire Stale Requests (every day at 08:30)
Campaigns expire after 7 days. This job marks them as `expired` so follow-ups stop.

---

## What Attachments Can It Parse?

### Both answers AND evidence can come as attachments

There are **two ways** a customer can provide information:

| Method | Example | Supported? |
|---|---|---|
| Write answers in the email body (plain text reply) | "Our company name is Acme Corp, we have 120 employees..." | ✅ Yes — primary method |
| Attach an Excel/Word file with answers filled in | A spreadsheet with question/answer columns | ✅ Yes — AI reads the file |
| Attach evidence documents (certificates, policies) | An ISO certificate PDF | ✅ Yes — matched to evidence tasks |
| All three combined in one reply | Text + a filled-in Word doc + a certificate PDF | ✅ Yes — all processed together |

The AI receives all content (email body text + parsed content from every attachment) at the same time and extracts everything in a single pass.

**So a customer can reply however they prefer** — write answers inline, attach a filled Excel form, or attach documents. The system handles all of it.

### Supported attachment formats

| File type | Parser | What it extracts |
|---|---|---|
| PDF | `pdfplumber` | All text content per page |
| Word (.docx) | `python-docx` | All paragraph text |
| Excel (.xlsx, .xls) | `openpyxl` | All cell values from all sheets |
| Images (.png, .jpg, .jpeg, .gif, .webp) | `Pillow` + base64 | Sent as image to Claude/Gemini for visual reading (scanned docs) |
| Other | — | Logged as unparseable, skipped |

Attachments are saved to: `storage/customers/emails/{log_id}/` inside the shared Docker volume.

---

## Database Tables

Five tables support the automation system in the `dna_app` schema:

### `automation_config` (singleton, 1 row, id=1)
Stores all global configuration. Read by both the backend API and the automation service.

### `customer_automation_config` (one row per customer, optional)
Per-customer overrides. If no row exists for a customer, global defaults apply.
- `customer_id` — FK to `customers.id`
- `send_to_emails` — TEXT[] override list
- `contact_name` — override for email greeting
- `preferred_language` — `'en'` or `'he'`
- `max_followups` — override for this customer
- `followup_delay_days` — override for this customer
- `enabled` — if false, no automated follow-ups for this customer

### `email_collection_requests`
One row per outbound campaign email sent.
- `token` — the `+collect_TOKEN` used to identify replies
- `questions_snapshot` — JSONB copy of all questions asked at send time
- `evidence_snapshot` — JSONB copy of all evidence tasks
- `campaign_number` — 1 for first send, 2 for first follow-up, etc.
- `status` — `pending` / `replied` / `expired`
- `expires_at` — 7 days after send

### `email_inbound_log`
One row per inbound email received.
- `from_email`, `subject`, `body_text`, `body_html`
- `attachments` — JSONB list of attachment metadata
- `status` — `received` → `processing` → `extracted` → `applied` / `skipped`
- `extraction_result` — raw JSON output from the LLM (answers, evidence_matches, notes, follow_up_keys). **Never overwritten once saved** — the `COALESCE` in the update prevents the final `'applied'` status update from clearing it.

### `email_extraction_items`
One row per extracted answer or evidence match.
- `item_type` — `answer` or `evidence`
- `placeholder_key` — for answers, which field was answered
- `extracted_value` — the actual answer text
- `confidence` — 0.0–1.0
- `status` — `auto_applied` / `pending` (review) / `accepted` / `rejected`
- `reviewed_by` / `reviewed_at` — human review audit trail

---

## Gmail vs SendGrid — Which Do You Need?

### The one-line answer

**Just fill in Gmail. That's all you need.** SendGrid is an optional upgrade for later.

> **DMARC Warning:** Do NOT configure `sendgrid_from_email` as a `@gmail.com` address. Gmail enforces a strict `p=reject` DMARC policy — if you send via SendGrid claiming to be from `@gmail.com`, Gmail (and most other email providers) will silently reject or drop the email. Use SendGrid only with a verified custom domain email (e.g., `compliance@yourcompany.com`).

---

### How email sending actually works

In the Admin → Automation config there is an **"Email Provider" toggle** with two options: **Gmail** or **SendGrid**.

```
┌─────────────────────────────────────────────┐
│  Email Provider                             │
│  ┌──────────────┐  ┌──────────────────┐    │
│  │ ✓  Gmail     │  │    SendGrid      │    │
│  └──────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────┘
```

**This toggle is the only thing that changes how outbound emails are sent.**

- Toggle = **Gmail** → the system sends campaign emails using your Gmail address + App Password via Gmail's SMTP server
- Toggle = **SendGrid** → the system sends campaign emails using your SendGrid API key via SendGrid's servers

**That's the entire difference between the two.** Everything else — reading replies, the IMAP listener, the token in the reply-to address — stays the same regardless of which toggle you pick.

---

### What about receiving? Always Gmail.

Customer replies are always received via Gmail IMAP — no matter which sending option you chose.

Why? Because the `Reply-To` on every outbound email is always set to:
```
yourname+collect_TOKEN@gmail.com
```

So replies always land in your Gmail inbox, and the IMAP listener reads from there.

There is no "SendGrid receive" mode. Gmail is always the inbox.

---

### So what do you actually need to configure?

**Scenario 1 — Start here (Gmail only):**

Fill in just these two fields, leave everything else at defaults:
1. `Gmail Address` → `yourname@gmail.com`
2. `Gmail App Password` → the 16-char password from Google Account → Security → App Passwords

Leave the toggle on **Gmail**. Done. The system will send AND receive using Gmail.

---

**Scenario 2 — Upgrade later (SendGrid for sending):**

If emails start going to spam, or you need to send more than ~500/day, or you want to send from a custom domain email like `compliance@yourcompany.com`:

1. Keep the Gmail fields as-is (still needed for receiving)
2. Also fill in `SendGrid API Key`, `SendGrid From Email` (**must be a verified custom domain address, not @gmail.com**), `SendGrid From Name`
3. Switch the toggle to **SendGrid**

Now: SendGrid sends outbound, Gmail IMAP still receives replies. Both are needed.

---

### Summary table

| | Just Gmail | Gmail + SendGrid |
|---|---|---|
| Sends outbound emails | ✅ Via Gmail SMTP | ✅ Via SendGrid |
| Receives replies | ✅ Gmail IMAP | ✅ Gmail IMAP (same) |
| Fields to fill in | Gmail address + App Password | All of the above + SendGrid key + from email |
| Sending limit | ~500 emails/day (free Gmail) | 100/day free, paid plans go much higher |
| From address | Must be your Gmail address | Must be verified custom domain (not @gmail.com!) |
| Deliverability | Good | Better (less likely to land in spam) |
| Recommended for | Getting started | Production use |

**If you don't know which to pick, pick Gmail. You can switch to SendGrid at any time without losing anything.**

---

## How the System Handles Irrelevant Emails

### It does skip emails it doesn't recognize — and marks them as read

The IMAP listener only fetches **UNSEEN** (unread) emails. For each one, it tries to identify the customer by:

1. Looking for the `+collect_TOKEN` in the `To:` / `Delivered-To:` header
2. If no token → matching the sender's `From:` address against all customer email fields

**If neither check succeeds** (random email, newsletter, GitHub notification, etc.):
- The email is **silently skipped** — no DB record created, no extraction queued
- The email is **marked as read (SEEN)** in the inbox
- A log line is written: `Inbound email from sender@example.com: no customer match, skipping`

This means the next poll will never see that email again (already read).

### What happens the very first time (old unread inbox)

If your Gmail inbox has hundreds of old unread emails when you first enable the automation service, the first IMAP poll will go through all of them:

- Each email is checked for a token or customer match
- None will match (they predate the system)
- All are marked as read
- None produce any DB entries
- After the first pass, the inbox is clean — all subsequent polls only see new emails

This is safe — the only side effect is that old unread emails become "read" in Gmail. If that bothers you, you can clean your inbox before enabling the service, or create a dedicated Gmail address just for DNA automation (recommended for production).

### Recommendation: use a dedicated Gmail address

Rather than using your personal or team inbox, create a fresh Gmail account like `dna-compliance@gmail.com`. Benefits:
- No risk of old emails interfering on first run
- Inbox stays clean — only DNA replies land there
- You can revoke access without affecting your main account

---

## Credential Encryption — How It Works

### What is encrypted and why

The Gmail App Password and SendGrid API key are sensitive credentials. If someone ever got read access to your database, you don't want them seeing those passwords in plain text. So they are **encrypted before being saved** to the database.

### What encryption is used

**Fernet symmetric encryption** (from Python's `cryptography` library). In simple terms:
- It uses a secret key to scramble the password into an unreadable string
- Only someone with the same secret key can unscramble it back to the original
- The algorithm (AES-128-CBC + HMAC-SHA256) is industry-standard and considered very secure

### Where the secret key comes from

The encryption key is derived from your app's `SECRET_KEY` — an environment variable set in `docker-compose.yml`.

```
SECRET_KEY=dna-secret-key-change-in-production   ← this is the default
```

The `SECRET_KEY` is run through SHA-256 to produce a fixed 32-byte value, which becomes the Fernet key. This means:
- **The same `SECRET_KEY` value → same encryption key → credentials can be decrypted**
- If you change `SECRET_KEY`, any previously saved credentials will become unreadable and you'll need to re-enter them in the Admin panel

### What it looks like in the database

Before encryption (plain text — old behavior, before this fix):
```
gmail_app_password = "abcd efgh ijkl mnop"
```

After encryption (new behavior):
```
gmail_app_password = "enc:gAAAAABn...long encrypted string...=="
```

The `enc:` prefix lets the system know this value is encrypted and needs to be decrypted before use.

### What the Admin UI shows

The UI always shows `••••••••` for these fields — you never see the actual value or the encrypted string. When you submit the form:
- If the field still shows `••••••••` → the saved encrypted value in the DB is kept unchanged
- If you type a new password → it gets encrypted and replaces the old value

### Important: change the SECRET_KEY in production

The default `dna-secret-key-change-in-production` is shared publicly (it's in the repo). Before going to production, change it in `docker-compose.yml`:

```yaml
environment:
  SECRET_KEY: "your-long-random-string-here-at-least-32-chars"
```

Generate a good one with: `python -c "import secrets; print(secrets.token_hex(32))"`

Both `dna-backend` and `dna-automation-service` must have the **same** `SECRET_KEY` value, otherwise the automation service cannot decrypt what the backend saved.

---

## SendGrid — What It Is and When to Use It

### SendGrid is for OUTBOUND ONLY

SendGrid is an email delivery service (like a professional SMTP relay). It handles **sending** campaign emails only.

**For receiving replies, IMAP is always used** — regardless of whether you send via Gmail SMTP or SendGrid. There is no "SendGrid receive" mode in the current setup.

### Why use SendGrid instead of Gmail?

- Better **deliverability** — emails less likely to land in spam
- You can use **any From address** (your company domain, not a Gmail address)
- SendGrid provides delivery receipts, open tracking, etc.
- Gmail SMTP has a daily sending limit (~500/day for free accounts)

### SendGrid Configuration

1. Sign up at [sendgrid.com](https://sendgrid.com) — free tier sends 100 emails/day
2. Settings → API Keys → Create API Key → Full Access → Copy it
3. Verify a Sender Identity (the email address you want to send from — **must be a custom domain, not @gmail.com**)
4. In **Admin → Automation**, set:

| Field | Value |
|---|---|
| Email Provider | `sendgrid` |
| SendGrid API Key | Your key from Step 2 |
| SendGrid From Email | Your verified sender email (e.g. `compliance@yourco.com`) |
| SendGrid From Name | `DNA Compliance` (or your company name) |
| Gmail Address | Still needed for IMAP receive (even when sending via SendGrid) |
| Gmail App Password | Still needed for IMAP receive |

> **Note:** Even if you use SendGrid for sending, you still need Gmail + App Password configured for the IMAP listener to read replies. The `Reply-To:` header is always set to `yourname+collect_TOKEN@gmail.com` so replies land in Gmail inbox where IMAP can pick them up.

---

## Configuration — Step by Step

### Step 1: Enable Gmail IMAP

In your Gmail account:
1. Settings → See all settings → Forwarding and POP/IMAP tab
2. Enable IMAP → Save Changes

### Step 2: Create a Gmail App Password

1. Google Account → Security
2. Under "How you sign in to Google" → 2-Step Verification (must be ON)
3. Scroll down → App passwords
4. Create app password → name it "DNA Automation"
5. Copy the 16-character password (you won't see it again)

### Step 3: Configure in DNA Admin Panel

Go to **Admin → Automation tab** and fill in:

| Field | Value |
|---|---|
| Enable Automation | Toggle ON |
| Email Provider | Gmail (or SendGrid) |
| Gmail Address | `yourname@gmail.com` |
| Gmail App Password | The 16-char password from Step 2 |
| IMAP Host | `imap.gmail.com` (default) |
| IMAP Port | `993` (default) |
| Poll Interval | How often to check inbox in seconds (60 default) |
| LLM Provider | Claude / Gemini / Groq |
| LLM Model | Auto-filled from your main AI config |
| Review Mode | Hybrid (recommended to start) |
| Auto-Apply Threshold | 0.85 (recommended) |
| Confidence Floor | 0.60 (recommended) |
| Follow-up Delay | 2 days |
| Max Follow-ups | 3 |

### Step 4: Send a Campaign

In the **Customer workspace → Automation tab**:
1. Select the ISO plan from the dropdown
2. (Optional) Click the gear icon to configure per-customer overrides
3. Click "Send Collection Email"
4. The system queues the campaign — the email is sent within seconds

### Step 5: Monitor Results

In the same **Customer workspace → Automation tab** you can see:
- How many campaigns were sent
- Received emails and their extraction status
- The review queue (items waiting for your approval)
- History of all auto-applied answers

---

## API Endpoints

| Method | Path | What it does |
|---|---|---|
| `GET` | `/api/v1/automation/config` | Read global config (passwords masked) |
| `PUT` | `/api/v1/automation/config` | Update global config settings |
| `GET` | `/api/v1/automation/{customer_id}/config` | Read per-customer automation overrides |
| `PUT` | `/api/v1/automation/{customer_id}/config` | Save per-customer automation overrides |
| `POST` | `/api/v1/automation/{customer_id}/send-collection` | Queue a campaign for a customer/plan |
| `GET` | `/api/v1/automation/{customer_id}/status` | Get campaigns, inbound emails, review queue |
| `GET` | `/api/v1/automation/review-queue` | Global review queue (all customers) |
| `POST` | `/api/v1/automation/review-item/{id}/accept` | Accept (apply) a queued answer |
| `POST` | `/api/v1/automation/review-item/{id}/reject` | Reject a queued answer |
| `POST` | `/api/v1/automation/trigger-imap-poll` | Manually trigger one IMAP inbox check right now |
| `POST` | `/api/v1/automation/webhooks/email-inbound` | SendGrid Inbound Parse webhook (future) |

---

## Build Progress

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | DB Schema (4 tables) | ✅ | automation_config, email_collection_requests, email_inbound_log, email_extraction_items |
| 2 | dna-automation-service skeleton + Docker | ✅ | automation-service/ — 11 files, separate container |
| 3 | Config API (backend) | ✅ | GET/PUT /api/v1/automation/config |
| 4 | Config UI (admin panel tab) | ✅ | AutomationConfig.tsx + admin page "Automation" tab |
| 5 | Email sender (Gmail SMTP / SendGrid) | ✅ | email_sender.py — branded HTML template, both providers |
| 6 | Campaign builder + send endpoint | ✅ | POST /api/v1/automation/{id}/send-collection → automation:send stream |
| 7 | IMAP listener + customer matcher | ✅ | email_listener.py — polls IMAP, +token extraction |
| 8 | AI extraction agent (Claude/Gemini/Groq) | ✅ | agents/email_extract_agent.py — all 3 providers, image vision |
| 9 | Attachment parser (PDF/image/docx/xlsx) | ✅ | attachment_parser.py — pdfplumber, python-docx, openpyxl, PIL |
| 10 | Review queue API | ✅ | GET review-queue, POST accept/reject |
| 11 | Dashboard Automation tab (frontend) | ✅ | AutomationTab.tsx — stats, send, review queue, history |
| 12 | Scheduled follow-ups + APScheduler | ✅ | scheduler.py — imap poll, daily follow-up, expire stale |
| 13 | Docker compose + rebuild | ✅ | dna-automation-service running |
| 14 | Per-customer automation config | ✅ | customer_automation_config table + API + UI gear modal |
| 15 | Hebrew (RTL) email support | ✅ | email_sender.py — _L localization dict, RTL HTML for 'he' language |
| 16 | apply_answer() ordering fix | ✅ | Task updated BEFORE placeholder → trigger sees answered_via/answer correctly |
| 17 | extraction_result COALESCE fix | ✅ | Final 'applied' update no longer overwrites saved LLM JSON |

---

## Key Files

```
automation-service/
├── main.py                        Entry point — starts all components
├── config.py                      Env vars (DB, Redis, LLM keys, storage path)
├── db_client.py                   All PostgreSQL operations (incl. apply_answer)
├── email_sender.py                Gmail SMTP + SendGrid outbound, Hebrew/EN support
├── email_listener.py              IMAP inbox polling
├── attachment_parser.py           PDF/Word/Excel/image text extraction
├── stream_consumer.py             Redis stream workers (send + extract)
├── scheduler.py                   APScheduler (IMAP poll, follow-ups, expire)
├── agents/
│   └── email_extract_agent.py     ← AI AGENT — LLM answer extraction
├── Dockerfile
└── requirements.txt

dashboard/backend/app/routes/
└── automation.py                  REST API endpoints (global + per-customer config)

dashboard/frontend/src/components/admin/
├── AutomationConfig.tsx           Admin panel global config UI
└── AutomationTab.tsx              Customer workspace automation tab + per-customer config modal

db/migrations/
└── 002_automation.sql             Original 4 tables

dashboard/migrations/
└── 011_customer_automation_config.sql   Per-customer overrides table
```
