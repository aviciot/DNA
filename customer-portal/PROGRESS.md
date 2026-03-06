# Customer Portal — Build Progress

## Status: 🟡 In Progress

---

## ✅ Done

### Infrastructure
- [x] `customer-portal/` folder created
- [x] `ARCHITECTURE.md` — full architecture, network isolation, security, features
- [x] `db/migrations/004_customer_portal.sql` — `portal_activity_log` table + `portal_user` with minimal grants

### Backend (`customer-portal/backend/`)
- [x] `pyproject.toml` — uv project, Python 3.12
- [x] `Dockerfile` — uv-based, installs libmagic
- [x] `.env.example`
- [x] `app/config.py` — pydantic-settings, all env vars, no hardcoded values
- [x] `app/db.py` — asyncpg pool, `validate_token()` dependency, `log_activity()`
- [x] `app/upload.py` — full 5-layer upload pipeline (size, filename, mime/magic, ClamAV, storage)
- [x] `app/routes/portal.py` — all endpoints:
  - `GET /portal/auth?token=` → set httpOnly cookie → redirect
  - `POST /portal/logout`
  - `GET /portal/me`
  - `GET /portal/progress`
  - `GET /portal/questions`
  - `POST /portal/answer`
  - `POST /portal/upload/{task_id}`
  - `GET /portal/history`
  - `POST /portal/relink`
- [x] `app/main.py` — FastAPI app, CORS, lifespan

### Frontend (`customer-portal/frontend/`)
- [x] `package.json` — Next.js 14, Tailwind, TypeScript
- [x] `next.config.js` — API rewrite to backend
- [x] `tsconfig.json`, `tailwind.config.js`, `postcss.config.js`
- [x] `Dockerfile`
- [x] `src/app/layout.tsx` — root layout
- [x] `src/app/globals.css` — Tailwind base
- [x] `src/app/page.tsx` — root redirect (token → `/api/portal/auth`, else → `/expired`)
- [x] `src/app/portal/page.tsx` — server component, fetches me/progress/questions
- [x] `src/app/expired/page.tsx` — expired link page + re-link form
- [x] `src/components/PortalClient.tsx` — main client shell, tabs, header with progress bar
- [x] `src/components/ProgressPanel.tsx` — stats grid, timeline, consultant card
- [x] `src/components/QuestionList.tsx` — question cards, answer input, file upload
- [x] `src/components/ChatWidget.tsx` — adapted from dashboard, cookie auth, customer-scoped prompts

---

## 🔲 TODO

### docker-compose.yml updates
- [x] Add `portal-network` and `portal-db-network` networks
- [x] Add `portal-clamav` service
- [x] Add `customer-portal-backend` service (networks: portal-network, portal-db-network)
- [x] Add `customer-portal-frontend` service (networks: portal-network)
- [x] Update `dna-postgres` to join `portal-db-network`
- [x] Update `dna-redis` to join `portal-db-network`
- [x] Add `clamav-db`, `portal-tmp`, `portal-storage` volumes
- [x] Add portal env vars to `.env.example`

### Backend — Chat WebSocket
- [x] `app/routes/chat.py` — WS `/portal/chat` with LLM streaming (groq/anthropic/gemini, reads from `llm_providers` table, decrypts key with Fernet)
- [x] `app/config.py` — added `secret_key` for Fernet decryption
- [x] Chat router wired into `app/main.py`

### automation-service
- [x] `stream_consumer.py` — passes `portal_url` to `send_campaign_email`
- [x] `config.py` — added `PORTAL_URL` env var
- [x] `docker-compose.yml` — `PORTAL_URL` added to automation-service env
- [x] `.env.example` — `PORTAL_URL=http://localhost:4000`

### Testing
- [ ] Run migration 004 against dev DB
- [ ] Smoke test token exchange → cookie → portal page
- [ ] Test answer submission
- [ ] Test file upload (with and without ClamAV)

---

## Notes
- Chat WS endpoint exists in routes but has no LLM backend yet — returns placeholder
- ClamAV: `REQUIRE_AV_SCAN=false` in dev to skip until container is running
- `portal_user` password must be changed before production
- Frontend API calls go through Next.js rewrite (`/api/portal/*` → backend) — no CORS issues
