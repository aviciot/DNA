# DNA Project — Development Rules & Architecture

## What This Product Is
DNA is an AI-powered ISO certification operations platform.
It helps compliance consultants manage enterprise customers through the full ISO certification journey — from document creation to evidence collection to final approval.

**Core value proposition:**
- Upload an ISO standard PDF → AI automatically builds all compliance document templates
- Templates contain `{{placeholders}}` — unique data points needed from the customer
- Placeholders are deduplicated across all documents — fill once, applies everywhere
- Multiple collection channels: manual interview, email automation, customer portal (future)
- Full audit trail: every answer, every version, every approval is tracked

**Users:**
- Admin (1-3 people): manages ISO library, templates, customers, assigns plans
- Regular user: fills customer data, manages tasks, tracks progress per customer

**Key entities (DB):**
- `customers` — companies being certified
- `iso_standards` — the certification standards (ISO 27001, etc.)
- `customer_iso_plans` — a customer enrolled in a specific ISO standard
- `templates` — compliance documents with fixed content + `{{placeholder}}` gaps
- `customer_documents` — a template instance for a specific customer/plan
- `customer_placeholders` — deduplicated list of ALL unique data points needed across all templates for a plan
- `customer_profile_data` — the collected answers (shared pool — fill once, auto-fills all documents)
- `customer_tasks` — work items to collect each placeholder value
- `task_resolutions` — how each task was resolved (answer, evidence, file)

**Automation hooks on templates:**
- `automation_source` — which system could auto-fill this (hr_system, asset_inventory, ad_directory, etc.)
- `trigger_event` — when it should be triggered (employee_onboarding, annual_review, incident, etc.)
- `auto_fillable` — boolean, whether AI/integration can fill it without human input
These exist to support future integrations. Do NOT remove them.

---

## Architecture

### Services
| Service | Tech | Port | Purpose |
|---|---|---|---|
| `dna-frontend` | Next.js 14 | 3007 | Admin + user UI |
| `dna-backend` | FastAPI | 3010 | Main API (customers, templates, ISO, tasks) |
| `dna-auth` | FastAPI | 3011 | Auth service (JWT, sessions) |
| `dna-ai-service` | Python worker | — | AI template builder, stream consumer |
| `dna-postgres` | PostgreSQL 16 | 3012 | Main database (schemas: auth, dna_app) |
| `dna-redis` | Redis 7 | 6379 | Task queue, pub/sub for AI progress |

### DB Schemas
- `auth` — users, roles, sessions
- `dna_app` — everything else (customers, templates, ISO standards, tasks, etc.)

### Frontend Structure
- `src/app/` — Next.js pages (App Router)
- `src/components/admin/` — admin panel components
- `src/components/` — shared components (AppShell, ChatWidget, etc.)
- `src/stores/` — Zustand auth store
- `src/lib/api.ts` — API client

### API Base URL
Always use `process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3010"` — never hardcode ports.

---

## File Editing Rules
- ALWAYS edit files on disk (via IDE or file tools), NEVER inside containers via `docker exec`
- Disk files ARE the container files (bind mounts) — but restart is still required to pick up changes

## Restart Requirements
| Service | After code change | Reason |
|---|---|---|
| `dna-frontend` | `docker compose restart dna-frontend` | `.next` is a separate Docker volume — hot reload does NOT work reliably |
| `dna-backend` | `docker compose restart dna-backend` | uvicorn reload not reliable in container |
| `dna-auth` | `docker compose restart dna-auth` | same |
| `dna-ai-service` | `docker compose restart dna-ai-service` | no auto-reload |
| `dna-postgres` | migration file + `docker compose down -v` for schema changes | |
| `dna-redis` | no code | |

**Rule: after ANY file change, restart the relevant service. Do not assume hot reload works.**

---

## Git Discipline
- After EVERY completed feature or fix: `git add -A && git commit -m "..."`
- Never leave working code uncommitted
- Push after each session: `git push`
- Current branch: `feature/template-preview-system`

---

## DB Discipline
- **Every schema change MUST update `DNA/db/init/01-init.sql`** — this is the single source of truth for the DB schema
- If you add a column, table, index, or constraint anywhere, update `01-init.sql` immediately in the same commit
- To apply schema changes to a running environment: `docker compose down -v && docker compose up -d` (destroys data — dev only)
- Never let the running DB drift from `01-init.sql`

---

## Known Issues / Gotchas
- `v_templates_with_details` view exists in DB but returns all NULLs — query `templates` table directly
- `ai_metadata` in `iso_standards` is stored as JSON string by asyncpg — parse it in the route, not at insert
- All frontend API calls must use `NEXT_PUBLIC_API_BASE_URL` env var (port 3010)
- `iso_standards` has `UNIQUE(code, language)` — one card per standard per language
