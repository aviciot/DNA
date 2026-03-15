# Background Services & Schedulers

How the system's background work is structured — what runs, where, and when.

---

## Overview: 2 Services, Each With Internal Loops

There is no standalone scheduler container. Background work is split across two Docker services, each running multiple loops inside a single Python process.

```
dna-automation-service
  ├── AutomationConsumer   (Redis stream loop — event-driven)
  └── AutomationScheduler  (APScheduler — time-driven)

dna-ai-service
  ├── StreamConsumer       (Redis stream loop — event-driven)
  └── run_cleanup_loop     (asyncio loop — every 5 min)
```

---

## dna-automation-service

Entry point: `automation-service/main.py`
Both components start in the same process as separate asyncio tasks.

---

### AutomationConsumer (`stream_consumer.py`)

Polls Redis streams every 0.5 seconds. Processes work that is **triggered on demand** by the backend or scheduler.

| Stream | What triggers it | What it does |
|---|---|---|
| `automation:send` | Backend (admin clicks Send) or `_followup_job` | Sends a campaign or follow-up email via SMTP/SendGrid |
| `automation:extract` | IMAP poll finds a new inbound email | Runs LLM extraction on email body, applies answers to tasks |
| `automation:imap_trigger` | Manual trigger from admin | Forces an immediate IMAP poll |
| `automation:iso360_template` | Admin clicks "Generate ISO360 Templates" | Forwards job to `ai:iso360_template` in ai-service |
| `automation:iso360_adjustment` | `_iso360_adjustment_check_job` or admin trigger | Forwards job to `ai:iso360_adjustment` in ai-service |

---

### AutomationScheduler (`scheduler.py`)

APScheduler instance running inside the same process. Handles **time-based** recurring work.

| Job ID | Schedule | What it does |
|---|---|---|
| `imap_poll` | Every 60s | Polls IMAP inbox for new customer reply emails |
| `daily_followup` | Daily 09:00 | Finds campaigns awaiting reply past delay threshold → pushes to `automation:send` |
| `expire_stale` | Daily 08:30 | Sets `email_collection_requests.status = 'expired'` for past-due requests |
| `notification_sender` | Every 5 min | Reads pending rows from `customer_tasks` (type=`notification`) → generates email via LLM → sends |
| `iso360_annual` | Daily 07:00 | Creates annual document review tasks for ISO360 plans whose reminder date = today |
| `iso360_adjustment_check` | Every 6 hours | Finds ISO360 plans that hit onboarding threshold and haven't been personalized → pushes to `automation:iso360_adjustment` |

**Important:** APScheduler has no persistence backend. Jobs are registered in memory on startup. If the container restarts, the next run is calculated from the restart time — a daily job that fires at 09:00 will be skipped if the container restarts at 09:01 and hasn't fired yet.

---

### How follow-up emails flow

```
daily_followup job (09:00)
  → queries DB: campaigns pending + past delay + under max_followups
  → pushes message to Redis: automation:send

AutomationConsumer picks up automation:send
  → calls send_campaign_email()
  → writes email_collection_requests record to DB
  → sends email via SMTP/SendGrid
```

---

### How ISO360 notification emails flow

```
iso360_annual job (07:00)  OR  admin triggers activity
  → inserts customer_task (type='notification', notes='iso360_reminder') into DB

notification_sender job (every 5 min)
  → reads pending notification tasks from DB
  → calls generate_notification_email() (LLM)
  → calls send_notification_email() (SMTP)
  → marks task as completed in DB
```

The notification path goes through the **DB queue** (not Redis), so it survives a container restart — the pending task row is still there when the service comes back up.

---

## dna-ai-service

Entry point: `ai-service/main.py`
Both components start as separate asyncio tasks.

---

### StreamConsumer (`stream_consumer.py`)

Handles heavy LLM jobs pushed from automation-service or the backend.

| Stream | What it does |
|---|---|
| `ai:iso_build` | Builds ISO standard — generates templates, placeholder dictionary, recurring_activities |
| `ai:iso360_template` | Generates 34 platform ISO360 activity templates for a standard |
| `ai:iso360_adjustment` | Personalizes ISO360 templates per customer using their Q&A context |

---

### run_cleanup_loop (`cleanup_job.py`)

Plain `while True` + `asyncio.sleep(300)` — not APScheduler.

Every 5 minutes:
- Marks `ai_tasks` rows stuck in `processing` > 15 min (45 min for `iso_build`) as `failed`
- Marks `ai_tasks` rows stuck in `pending` > 20 min as `failed`

This prevents the admin UI from showing a task spinning forever after a worker crash.

---

## Summary: Who Owns What

| Responsibility | Owned by | Mechanism |
|---|---|---|
| Send campaign emails | automation-service | Redis stream |
| Send follow-up emails | automation-service | APScheduler → Redis stream |
| Receive/parse inbound emails | automation-service | APScheduler (IMAP poll) → Redis stream |
| Send notification/welcome/reminder emails | automation-service | APScheduler → DB queue → notif job |
| ISO360 annual review tasks | automation-service | APScheduler → DB insert |
| ISO360 adjustment trigger | automation-service | APScheduler → Redis stream → ai-service |
| ISO build (LLM) | ai-service | Redis stream |
| ISO360 template generation (LLM) | ai-service | Redis stream |
| ISO360 customer adjustment (LLM) | ai-service | Redis stream |
| Zombie task cleanup | ai-service | asyncio loop |

---

## Known Limitation

See `docs/automation-service-reboot-analysis.md` for full details.
Short version: Redis stream messages that are mid-processing at restart time get stranded (missing `XAUTOCLAIM` on startup). The notification email path is safe because it uses a DB queue instead of Redis.
