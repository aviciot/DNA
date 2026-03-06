# Customer Portal — Architecture & Guidelines

## Overview

A public-facing self-service portal where customers receive a tokenized link and can:
- View their ISO certification progress
- Answer compliance questions (same interview-style UI as dashboard)
- Upload evidence files
- Use an AI chat assistant for guidance (backed by MCP tools scoped to their data)

Completely isolated from the internal dashboard — separate containers, separate network exposure.

---

## Container Architecture

```
customer-portal/
  backend/    → FastAPI (uv)       port 4010
  frontend/   → Next.js            port 4000
```

---

## Network Isolation — Critical

This is the most important design decision. The portal is **internet-facing**. The DNA dashboard is **internal only**.

### The Problem With a Shared Network

The current DNA stack runs on a single Docker bridge network `dna-network`. Every service on that network can reach every other service by container name — `dna-backend`, `dna-auth`, `dna-postgres`, `dna-redis` are all reachable from any container on `dna-network`.

If the portal backend joins `dna-network`, a compromised portal container could:
- Hit `http://dna-backend:3010/api/v1/admin/...` directly (no auth needed from inside the network)
- Connect to `dna-postgres:5432` with the shared DB credentials
- Hit `dna-auth:3011` and probe auth endpoints
- Read from `dna-redis` which holds session data and job queues

**The portal must NOT join `dna-network`.**

### Solution — Two Networks, DB as the Bridge

```
                    ┌─────────────────────────────────┐
  INTERNET          │  dna-network  (internal only)   │
      │             │                                 │
      │             │  dna-frontend   :3001           │
      │             │  dna-backend    :3010           │
      │             │  dna-auth       :3011           │
      │             │  dna-ai-service                 │
      │             │  dna-automation-service         │
      │             │  dna-redis      :6379  ◄──┐     │
      │             │  dna-postgres   :5432  ◄──┼──┐  │
      │             └───────────────────────────┼──┼──┘
      │                                         │  │
      │             ┌───────────────────────────┼──┼──┐
      │             │  portal-network (isolated) │  │  │
      ├──▶ :4000    │  portal-frontend           │  │  │
      │             │       │                   │  │  │
      └──▶ :4010    │  portal-backend ───────────┘  │  │
                    │       │  (portal-db-network)   │  │
                    │       └───────────────────────┘  │
                    └──────────────────────────────────┘
```

Three networks:
- `dna-network` — existing internal network, dashboard services only
- `portal-network` — portal frontend + backend only
- `portal-db-network` — portal backend + postgres + redis only (no dashboard services on this network)

`dna-postgres` and `dna-redis` join **both** `dna-network` and `portal-db-network`.  
The portal backend can reach the DB but **cannot reach dna-backend, dna-auth, or any other dashboard service**.  
The portal frontend can only reach the portal backend.

### docker-compose network config

```yaml
networks:
  dna-network:          # existing — dashboard services only
    driver: bridge
  portal-network:       # portal frontend ↔ portal backend
    driver: bridge
  portal-db-network:    # portal backend ↔ postgres + redis only
    driver: bridge

services:
  dna-postgres:
    networks: [dna-network, portal-db-network]   # shared DB, two networks

  dna-redis:
    networks: [dna-network, portal-db-network]   # shared cache, two networks

  portal-backend:
    networks: [portal-network, portal-db-network]  # NO dna-network
    # Can reach: postgres, redis
    # Cannot reach: dna-backend, dna-auth, dna-frontend, dna-ai-service

  portal-frontend:
    networks: [portal-network]                     # NO dna-network, NO portal-db-network
    # Can reach: portal-backend only
```

### DB User Isolation (additional hardening)

The portal backend uses a **separate, read-limited Postgres user** — not `dna_user`:

```sql
CREATE USER portal_user WITH PASSWORD '...';
-- Only the tables the portal needs:
GRANT SELECT, UPDATE ON dna_app.email_collection_requests TO portal_user;
GRANT SELECT ON dna_app.customer_tasks TO portal_user;
GRANT SELECT ON dna_app.customers TO portal_user;
GRANT INSERT, UPDATE ON dna_app.customer_profile_data TO portal_user;
GRANT INSERT ON dna_app.portal_activity_log TO portal_user;
-- Nothing else — no access to automation_config, llm_providers, templates, etc.
```

Even if the portal backend is fully compromised, the attacker can only read/write the tables above.

### Redis Isolation

Portal backend uses Redis DB index `2` (dashboard uses `0`). Not perfect isolation but limits blast radius — portal cannot read dashboard session keys or job queues.

For production: run a separate Redis instance for the portal.

---

## Port Allocation (4000–4100 range)

| Service                  | Port |
|--------------------------|------|
| Portal frontend (Next.js)| 4000 |
| Portal backend (FastAPI) | 4010 |
| Portal MCP server        | 4020 |
| Reserved                 | 4021–4100 |

---

## Authentication — Token Only, No Auth Service

**No auth-service dependency.** The token IS the credential.

- Token is a UUID stored in `email_collection_requests.token`
- Token scope: customer can only see/modify data belonging to their `customer_id` + `plan_id`
- Backend validates on every request: token exists + not expired + status != 'cancelled'

### httpOnly Cookie — Required

The token must NOT live in JavaScript memory, localStorage, or stay in the URL.
An httpOnly cookie is the correct storage — JS cannot read it, so XSS cannot steal it.

**Flow:**
```
1. Customer clicks link: GET /portal?token=<uuid>
2. Backend validates token → sets httpOnly cookie:
     Set-Cookie: portal_token=<uuid>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800
3. Backend redirects to /portal (token removed from URL — gone from history/logs)
4. All subsequent requests: browser sends cookie automatically
5. Backend reads token from cookie only — never from URL params or headers
```

**Cookie attributes:**
- `HttpOnly` — JS cannot read it (blocks XSS token theft)
- `Secure` — HTTPS only (required in production)
- `SameSite=Strict` — blocks CSRF (cookie not sent on cross-site requests)
- `Max-Age=604800` — 7 days, matches token `expires_at`
- `Path=/` — scoped to portal only

**On expiry:** portal shows a friendly "This link has expired — contact your consultant" page.

**On logout / completion:** backend clears the cookie with `Max-Age=0`.

---

## Logging — Required, Not Optional

The portal is internet-facing. Logging is mandatory for security and audit.

All portal activity is written to a `portal_activity_log` table:

- Every token validation attempt — success, expired, not found (with IP + user-agent)
- Every answer submitted (token, question key, timestamp — not the value itself)
- Every file uploaded (token, task_id, filename, size)
- Every chat session start/end
- Rate limit hits

This table is in `dna_app` schema, writable by `portal_user` only via INSERT — no UPDATE/DELETE.
The DNA dashboard team can query it to see customer engagement, detect abuse, and audit submissions.

The DNA dashboard itself should have strong auth (JWT + refresh tokens via `dna-auth`) and can be locked down further to internal network / VPN only since it never needs to be public.

---

## File Upload Security

File uploads from the public internet are the highest-risk operation in the portal.
Every uploaded file goes through a multi-layer pipeline before it touches storage.

### Layer 1 — Request-Level Rejection (before reading the file)

- Max size: `20MB` enforced at the HTTP layer (Content-Length check before streaming)
- Max files per upload request: `5`
- Rate limit: `10 uploads per token per hour` (Redis counter)
- Only multipart/form-data accepted — raw body uploads rejected

### Layer 2 — Filename Sanitization

The original filename is NEVER used for storage. Ever.

```python
# What we store:
storage_name = f"{task_id}_{uuid4().hex[:8}_{sanitized_ext}"
# sanitized_ext = extension extracted from mime type, not from filename
```

- Original filename kept only in DB metadata (for display)
- No path separators, no `..`, no null bytes allowed even in the display name
- Storage path is always: `/storage/customers/{customer_id}/evidence/{task_id}/`

### Layer 3 — MIME Type & Extension Blocklist

Two checks run independently — both must pass:

**Allowed extensions (allowlist — everything else rejected):**
```
.pdf  .docx  .doc  .xlsx  .xls  .pptx  .ppt
.png  .jpg   .jpeg .gif   .webp .tiff
.txt  .csv   .zip  .tar.gz
```

**Hard-blocked regardless of extension:**
```
.exe  .bat  .cmd  .sh   .ps1  .psm1  .psd1
.js   .ts   .py   .rb   .php  .pl    .lua
.jar  .war  .class .dll  .so   .dylib
.msi  .deb  .rpm  .dmg  .app
.vbs  .wsf  .hta  .scr  .com  .pif
.html .htm  .svg  (SVG can contain JS)
```

**Magic bytes check (python-magic):**  
The declared MIME type is verified against the actual file magic bytes — a `.pdf` that is actually a PE executable is rejected even if the extension is correct.

### Layer 4 — Antivirus Scan (ClamAV)

A `clamav` sidecar container runs in `portal-network`. Every uploaded file is streamed to ClamAV via `clamd` socket before being written to final storage.

```
Upload received → temp file written to /tmp/uploads/ → ClamAV scan
    ├── CLEAN  → move to /storage/customers/.../evidence/
    └── INFECTED / ERROR → delete temp file, return 422, log incident
```

**ClamAV container:**
```yaml
portal-clamav:
  image: clamav/clamav:stable
  networks: [portal-network]
  volumes:
    - clamav-db:/var/lib/clamav      # virus definition DB (auto-updated)
    - portal-tmp:/tmp/uploads        # shared temp volume with portal-backend
  environment:
    - CLAMAV_NO_FRESHCLAMD=false     # keep definitions updated
```

The portal backend connects to ClamAV via `clamd` TCP socket — no internet access needed from the backend container.

**On ClamAV unavailable:** uploads are REJECTED (fail closed, not fail open). A config flag `REQUIRE_AV_SCAN=true` controls this — default true in production.

### Layer 5 — Storage Isolation

- Uploaded files land in a volume mounted ONLY to `portal-backend` and `dna-automation-service`
- The volume is NOT mounted to `portal-frontend` — files are never served directly from the portal
- Files are served back to the customer only via a signed, time-limited URL generated by the backend
- The storage volume has `noexec` mount flag — OS will not execute any file on it

### Upload Pipeline Summary

```
POST /portal/upload/{task_id}
  │
  ├─ 1. Token valid? Rate limit ok? Size ok?          → 401/429/413 if not
  ├─ 2. Write to /tmp/uploads/{random_name}           (temp, not final storage)
  ├─ 3. Magic bytes check + extension allowlist       → 422 if fail
  ├─ 4. ClamAV scan via clamd socket                  → 422 + log if infected
  ├─ 5. Move to /storage/customers/{id}/evidence/{task_id}/{uuid}.{ext}
  ├─ 6. Insert DB record (original_name, storage_path, size, scan_result)
  └─ 7. Log to portal_activity_log                    → always
```

### Dependencies

```
python-magic      # magic bytes detection
clamd             # Python client for ClamAV daemon
```

---

## Backend — FastAPI (uv)

**Runtime:** Python 3.12, managed with `uv`

**Endpoints:**

```
GET  /portal?token={token}          → validate, set httpOnly cookie, redirect to /portal
GET  /portal                        → main portal (reads token from cookie)
GET  /portal/questions              → pending questions
GET  /portal/progress               → task completion stats
POST /portal/answer                 → submit answer
POST /portal/upload/{task_id}       → upload evidence file
WS   /portal/chat                   → WebSocket chat (MCP-backed)
POST /portal/logout                 → clear cookie
```

No token in URL after the initial redirect. No `X-Portal-Token` header.

**Key rules:**
- Every handler calls `validate_token(token)` first — raises 401 if invalid/expired
- All DB queries are scoped with `customer_id` from the validated token row
- Rate limiting: 60 req/min per token (via Redis)
- File uploads: max 20MB, stored to `/app/storage/customers/{customer_id}/portal-uploads/`

---

## MCP Server — Customer-Scoped Tools

The portal backend runs a lightweight MCP server (port 4020) that exposes tools scoped to the customer's data:

```
get_my_progress(token)          → completion %, pending count, answered count
get_pending_questions(token)    → list of unanswered questions with hints
get_question_detail(token, key) → full question + context + examples
submit_answer(token, key, value)→ save answer (same path as POST /answer)
get_iso_guidance(standard, topic) → pull from ISO reference docs
```

The AI chat uses these tools so it can:
- Tell the customer exactly what's pending
- Help them phrase answers correctly
- Pull relevant ISO standard guidance
- Submit answers on their behalf when they confirm via chat

The MCP server does NOT expose any cross-customer tools — token is always required and enforced.

---

## Frontend — Next.js

**Port:** 4000  
**Style:** Same design system as dashboard (Tailwind, same color palette, same component patterns)

**Pages:**
```
/                         → redirect to /portal/[token] if token in URL, else "invalid link"
/portal/[token]           → main portal page
/portal/[token]/expired   → link expired page
```

**Main portal page layout:**
```
┌─────────────────────────────────────────────┐
│  DNA Logo   |  [Customer Name] — ISO [std]  │
│             |  Progress: ██████░░░░ 60%     │
├─────────────────────────────────────────────┤
│                                             │
│  [Progress Overview]  [Answer Questions]    │
│                                             │
│  Question cards (same interview-style UI)   │
│  - Text input / dropdown / date picker      │
│  - File upload for evidence tasks           │
│  - "Save" per question or bulk submit       │
│                                             │
└─────────────────────────────────────────────┘
                              [💬 AI Assistant] ← ChatWidget (reused, token-auth variant)
```

**ChatWidget reuse:**
- Copy `ChatWidget.tsx` from dashboard, adapt WebSocket URL to portal backend (`NEXT_PUBLIC_PORTAL_WS_URL`)
- Replace JWT auth header with `X-Portal-Token` header
- Change suggested prompts to customer-facing ones:
  - "What information do I need to provide?"
  - "Help me answer question about [topic]"
  - "What is ISO 27001 asking for here?"
  - "Submit my answer for [question]"

---

## Environment Variables

**Backend (`customer-portal/backend/.env`):**
```
DATABASE_URL=postgresql://...          # same dna-postgres
REDIS_URL=redis://dna-redis:6379/2     # separate DB index from main app
SECRET_KEY=                            # same as main app (for Fernet decrypt if needed)
DATABASE_APP_SCHEMA=dna_app
PORTAL_TOKEN_MAX_AGE_DAYS=7
MAX_UPLOAD_SIZE_MB=20
STORAGE_PATH=/app/storage
```

**Frontend (`customer-portal/frontend/.env.local`):**
```
NEXT_PUBLIC_PORTAL_API_URL=http://localhost:4010
NEXT_PUBLIC_PORTAL_WS_URL=ws://localhost:4010
```

No hardcoded URLs or ports anywhere — all via env vars.

---

## Docker Services

```yaml
# Added to root docker-compose.yml
customer-portal-backend:
  build: ./customer-portal/backend
  ports: ["4010:4010"]
  env_file: ./customer-portal/backend/.env
  networks: [portal-network, portal-db-network]   # NOT dna-network
  volumes:
    - portal-tmp:/tmp/uploads
    - portal-storage:/app/storage
  depends_on: [dna-postgres, dna-redis, portal-clamav]

customer-portal-frontend:
  build: ./customer-portal/frontend
  ports: ["4000:4000"]
  networks: [portal-network]                       # NOT dna-network
  environment:
    - NEXT_PUBLIC_PORTAL_API_URL=http://customer-portal-backend:4010
    - NEXT_PUBLIC_PORTAL_WS_URL=ws://customer-portal-backend:4010
  depends_on: [customer-portal-backend]

portal-clamav:
  image: clamav/clamav:stable
  networks: [portal-network]
  volumes:
    - clamav-db:/var/lib/clamav
    - portal-tmp:/tmp/uploads

dna-postgres:
  networks: [dna-network, portal-db-network]       # joins both

dna-redis:
  networks: [dna-network, portal-db-network]       # joins both
```

---

## Security Boundaries

| What                          | Allowed | Reason |
|-------------------------------|---------|--------|
| Customer sees other customers | ❌ | All queries scoped to token's customer_id |
| Customer accesses admin routes| ❌ | Separate container, no shared router |
| Expired token works           | ❌ | Checked on every request |
| Token brute-force             | ❌ | Rate limited + tokens are UUIDs (128-bit) |
| File upload path traversal    | ❌ | Filename sanitized, stored by task_id |
| Chat leaks other customer data| ❌ | MCP tools enforce token scope |

---

## Features

### v1 — Launch

| Feature | Description | Data source |
|---------|-------------|-------------|
| Progress dashboard | Visual progress bar, % complete, pending vs answered count, certification target date | `customer_tasks`, `customer_plans` |
| Timeline view | What's done, what's blocking, estimated completion — not just a percentage | `customer_tasks` ordered by priority |
| Answer questions | Interview-style cards — text, date, dropdown inputs. Save per-question or bulk submit | `customer_tasks`, `customer_profile_data` |
| Evidence upload | File upload per evidence task, with status (uploaded / pending / accepted) | `customer_tasks` where type=evidence |
| Submission history | Read-only log: "You answered X on [date], uploaded Y on [date]" — builds trust, reduces support emails | `portal_activity_log` |
| Consultant card | Name + email of their assigned DNA consultant. Static display — no interaction | `customers.contact_name` |
| AI chat assistant | ChatWidget (reused from dashboard, token-scoped). Helps answer questions, explains ISO requirements, can submit answers on confirmation | MCP tools |
| Re-request link | "My link expired" form — enter email, get new token if email matches a customer record | `email_collection_requests` |

### v2 — After Launch

| Feature | Description | Notes |
|---------|-------------|-------|
| Notification center | Two feeds: **News** (DNA announcements, standard updates) and **For You** (personalized — LLM recommends next actions based on their specific gaps) | Needs `portal_notifications` table + LLM recommendation job |
| Document download | Download DNA-generated documents for their plan (policy drafts, etc.) | `ai-service` already generates these — just expose read endpoint |
| LLM-personalized recommendations | "For You" feed: AI looks at their pending tasks and suggests what to tackle first, with context | Runs as a background job, writes to `portal_notifications` |
| Multi-language support | Portal UI in customer's preferred language | i18n on Next.js, system prompt language hint to LLM |

### Explicitly Out of Scope

- In-portal document editing — that's the dashboard's job
- Multi-user / colleague invite — requires auth service
- Payment / billing
- Admin functions of any kind

---

## Build Order

1. `customer-portal/backend/` — FastAPI app with token validation + 5 endpoints + WS chat
2. `customer-portal/backend/mcp_server.py` — MCP tools (customer-scoped)
3. `customer-portal/frontend/` — Next.js app with portal page + adapted ChatWidget
4. Wire into `docker-compose.yml`
5. Update `automation-service/email_sender.py` to include portal link in outbound emails
