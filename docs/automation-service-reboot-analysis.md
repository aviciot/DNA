# Automation Service — Reboot Safety Analysis

What actually happens when `dna-automation-service` is restarted, and what edge cases exist.

---

## What the Service Owns

| Component | Type | State lives in |
|---|---|---|
| Redis stream consumer | Long-running loop | Redis (persistent) |
| APScheduler jobs | In-memory cron/interval | Memory only — lost on restart |
| IMAP email listener | Stateless poll | IMAP server (external) |
| DB connection pool | In-memory | Recreated on restart |
| Email sends in progress | In-flight | Redis stream message (pending list) |

---

## Scenario-by-Scenario Breakdown

---

### 1. Redis Stream Consumer (automation:send, automation:extract, etc.)

**What happens on reboot:**
Redis consumer groups use an ACK protocol. When a message is read with `XREADGROUP`, it enters the **Pending Entries List (PEL)** for that consumer. It only leaves PEL after `XACK` is called.

In the current code (`stream_consumer.py` line 114):
```python
await self._redis.xack(stream, group, msg_id)
```
The ACK happens **after** the handler function completes. So:

| Case | What happens on reboot |
|---|---|
| Message was read, handler finished, ACK sent | Safe — message is gone from PEL |
| Message was read, handler was mid-execution, reboot hits | Message stays in PEL as "pending" — **not automatically redelivered** |
| Message was never read | Safe — it's still in the stream, new consumer picks it up |

**The risk:** Mid-flight messages (email being sent, extraction running) get stuck in PEL forever after reboot. The new consumer instance gets a **new consumer ID** (random hex, line 48: `f"auto-worker-{uuid.uuid4().hex[:6]}"`), so it only reads `">"` (new messages), never picks up the old pending ones.

**Current state: This is a silent stuck-message bug that already exists.** After a reboot, any in-flight message at restart time is stranded. It won't error — it just never runs again.

**How to fix (recommended):**
At startup, before entering the consume loop, claim any pending messages older than N seconds from dead consumers using `XAUTOCLAIM` (Redis 7+) or `XPENDING` + `XCLAIM`:

```python
# On startup, reclaim pending messages older than 60s from any consumer in the group
await self._redis.xautoclaim(stream, group, self.consumer_id, min_idle_time=60000, start_id="0-0")
```
This is the standard pattern for reliable Redis stream consumers.

---

### 2. APScheduler Jobs (cron + interval)

**What happens on reboot:**
APScheduler jobs are defined in memory only — no persistence backend is configured. On restart, all jobs are re-registered from code and start on their next scheduled trigger time.

| Job | Schedule | Risk on reboot |
|---|---|---|
| `_followup_job` | Daily 09:00 | If reboot happens at 09:00, job may be skipped for the day |
| `_expire_stale_job` | Daily 08:30 | Same — skip for the day |
| `_iso360_annual_job` | Daily 07:00 | Same — annual reminder could be missed |
| `_notification_job` | Every 5 min | Low risk — next run within 5 min of restart |
| `_poll_imap_job` | Every 60 sec | Low risk — next run within 60 sec |
| `_iso360_adjustment_check_job` | Every 6 hours | Low risk — runs again within 6 hours |

**The real risk is the daily jobs.** If the container restarts between 07:00–09:00, the follow-up and annual jobs will not run until the next day.

**Current severity:** Low for most days, but it means a customer could miss a follow-up email or an ISO360 annual reminder on the reboot day.

**How to fix (recommended):**
The daily jobs are idempotent — they check DB state before acting (e.g., `source_year` dedup for annual tasks). Adding a "catch-up on startup" check is safe:

```python
# On startup: if today's daily jobs haven't run yet (check a Redis key), run them immediately
await self._maybe_run_daily_catchup()
```
A simple Redis key like `automation:daily_ran:{date}` set after each daily job run is enough.

---

### 3. Email Being Sent Mid-Flight

**What happens:**
`_handle_send()` calls `send_campaign_email()`, which talks to SMTP/SendGrid. If the reboot happens:

| Point of reboot | Result |
|---|---|
| Before SMTP call | Email not sent. Message stuck in PEL (see #1). Customer gets no email until manually resolved. |
| During SMTP handshake | SMTP connection drops. Email likely not delivered. Same PEL problem. |
| After SMTP succeeds, before DB write / XACK | Email is delivered to customer BUT the DB record is not written. The message stays in PEL. If reclaimed and retried, the email is sent **twice** to the customer. |

**The duplicate email risk** (after SMTP, before ACK) is the worst case here. It's rare but possible.

**How to handle:** The `create_collection_request` DB call happens before the SMTP send (by design — the record is written first, then email sent). So if the container crashes after the DB write but before SMTP completes, the record exists but the email wasn't sent — and a retry is safe. The reverse (SMTP sent but DB not written) is the dangerous window, and it's very narrow.

---

### 4. Extraction In Progress

Similar to email sending. If `_handle_extract()` is mid-LLM-call on reboot:
- The `email_inbound_log` row exists in DB (written before extraction starts)
- The extraction result is lost
- Message stays in PEL
- After reclaim and retry, the LLM call runs again — this is safe (idempotent from the customer's perspective)

---

### 5. ISO360 Adjustment / Template Jobs

These are forwarded to ai-service via Redis (`ai:iso360_template`, `ai:iso360_adjustment`). The automation-service handler is just a message relay — it's very fast. Risk of being mid-flight on reboot is very low. If it does happen, the message stays in PEL; reclaim + retry is safe (ai-service job dedup is handled there).

---

### 6. IMAP Listener

Stateless — polls IMAP server on each run. A reboot just means a gap of up to 60 seconds where no IMAP poll runs. The emails stay on the IMAP server and are picked up on the next poll. **No data loss risk.**

---

## Summary: Risk Levels

| Risk | Severity | Frequency | Currently handled? |
|---|---|---|---|
| Stranded PEL messages after reboot | Medium | Every reboot | No — needs XAUTOCLAIM at startup |
| Duplicate email (SMTP sent, before ACK) | Low | Rare | No — but window is tiny |
| Missed daily cron job (reboot at job time) | Low | Rare | No — APScheduler has no persistence |
| IMAP gap (up to 60s) | Very low | Every reboot | Acceptable — emails stay on server |
| ISO360 adjustment job stranded | Low | Every reboot | No — same PEL issue |

---

## Recommended Fix: XAUTOCLAIM at Startup

This one change fixes the most common reboot risk (stranded PEL messages) for all streams:

```python
# In AutomationConsumer.start(), after creating consumer groups:
for stream, group in STREAMS:
    try:
        # Reclaim any messages pending > 60s (from previous consumer instances that died)
        await self._redis.xautoclaim(
            stream, group, self.consumer_id,
            min_idle_time=60_000,  # 60 seconds idle
            start_id="0-0",
            count=100,
        )
        logger.info(f"XAUTOCLAIM on {stream}: reclaimed stale pending messages")
    except Exception as e:
        logger.warning(f"XAUTOCLAIM not available or failed for {stream}: {e}")
```

**Result:** On every restart, any message that was mid-flight at the time of the previous crash is immediately reclaimed and reprocessed. No manual intervention needed.

---

## What Doesn't Need Fixing

- **Database connection pool** — asyncpg reconnects cleanly on startup. No risk.
- **Redis connection** — reconnected on startup. No risk.
- **APScheduler memory loss** — acceptable trade-off unless the service restarts constantly. If that's happening, the real problem is instability, not scheduler persistence.
- **ISO360 activities themselves** — all data is in PostgreSQL. A reboot doesn't affect customer documents, tasks, or plan state.
