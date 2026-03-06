# Cloudflare Zero Trust — Auth Migration Plan

## Current Deployment (Local / Dev)

Everything runs on a single machine via Docker Compose. All services are on a shared Docker network. Ports are exposed directly to the host — there is no reverse proxy, no TLS, no firewall between the internet and the containers.

```
Developer Browser
    │
    ▼
localhost (direct port access)
    ├── :3001  dna-frontend      (Next.js, live volume mount)
    ├── :3010  dna-backend       (FastAPI, live volume mount)
    ├── :3011  auth-service      (FastAPI — login, token verify, user mgmt)
    ├── :4000  portal-frontend   (Next.js, baked into image)
    ├── :4010  portal-backend    (FastAPI, baked into image)
    ├── :5432  postgres          (single DB, schemas: dna_app / auth)
    ├── :6379  redis             (streams + pub/sub)
    ├── automation-service       (no exposed port — reads Redis streams)
    └── ai-service               (no exposed port — reads Redis streams)
```

**Key characteristics of current setup:**
- No TLS — all traffic is plain HTTP
- No reverse proxy — browser talks directly to container ports
- No rate limiting — endpoints like `/auth` are unprotected
- Auth is custom-built — `auth_service` issues JWTs, every backend request calls `/verify` over HTTP
- `dna-backend` + `dna-frontend` use live volume mounts (hot reload). `portal-backend` + `portal-frontend` bake code into image (require rebuild)
- All services share one Docker network (`portal-db-network`)

---

## Current State

### Dashboard (Internal Tool)
- **Auth service** (`auth_service/`, port 3011) — custom FastAPI service
- Login flow: `POST /api/v1/auth/login` → JWT access + refresh tokens → stored in `auth.sessions` table
- Token verification: every backend request calls `GET /api/v1/auth/verify` on the auth service → returns `X-User-Id`, `X-User-Email`, `X-User-Role` headers
- Roles: `admin`, `dna_operator`, `viewer` — enforced in `dashboard/backend/app/auth.py` via `require_admin` / `require_operator` dependencies
- Frontend: `authStore` holds JWT in memory, login page at `/login`

### Customer Portal (External, Customer-Facing)
- **Token-based, not password-based** — customers arrive via magic link (`/auth?token=<64-char-hex>`)
- Token validated against `customer_portal_access` table (1-year TTL, one per customer)
- Sets httpOnly cookie `portal_token` → all subsequent requests use cookie
- No username/password — customers don't have accounts

---

## Why Cloudflare Zero Trust

| Problem | CF Zero Trust Solves |
|---|---|
| Custom auth service is a maintenance burden | Replace with managed identity provider |
| JWT secrets must be rotated manually | CF handles key rotation |
| No MFA on dashboard | CF enforces MFA per policy |
| No IP/device posture checks | CF Access policies support geo, device, IdP |
| Dashboard exposed directly to internet | CF Tunnel removes open inbound ports |
| No SSO (each user needs a local account) | CF integrates with Google, Azure AD, Okta, etc. |

---

## Scope Decision

| Surface | CF Zero Trust? | Reason |
|---|---|---|
| Dashboard (dna-frontend + dna-backend) | **Yes — Access enforced** | Internal tool, staff only — OTP email or SSO |
| Customer Portal | **Yes — Tunnel only, no Access gate** | Public-facing; CF WAF + DDoS + TLS, magic-link auth unchanged |
| Automation service | **No** | Internal service, not user-facing |
| MCP server | **No** | Token-scoped per customer, not staff-facing |

---

## Architecture After Migration

```
Staff Browser
    │
    ▼
Cloudflare Access (OTP email / SSO)
    │  ← blocks unauthenticated requests at CF edge
    ▼
CF Tunnel (cloudflared)
    │
    ▼
Traefik (internal router)
    ├──► dna-frontend  :3001
    ├──► dna-backend   :3010   (CF JWT in Cf-Access-Jwt-Assertion header)
    └──► auth-service  :3011   (user/role management only)


Customer Browser
    │
    ▼
Cloudflare (Tunnel only — no Access gate)
    │  CF WAF + DDoS + Bot protection active
    ▼
Traefik (internal router)
    ├──► portal-frontend  :4000
    └──► portal-backend   :4010   (magic-link auth unchanged)
         └── rate limit on /auth via Traefik middleware
```

---

## What Changes

### 1. Dashboard backend — replace JWT verification with CF JWT validation

`dashboard/backend/app/auth.py` currently calls the auth service to verify tokens.
After migration it verifies the **Cloudflare Access JWT** directly (no network hop).

CF injects `Cf-Access-Jwt-Assertion` header on every request that passes Access.
The JWT is signed with CF's public keys (fetched from `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`).

New `verify_token` logic:
1. Read `Cf-Access-Jwt-Assertion` header (or fall back to `Authorization: Bearer` for API clients / local dev)
2. Verify signature against CF public keys (cached, refreshed on failure)
3. Extract `email` claim → look up user in `auth.users` to get `role`
4. Return `{user_id, email, role}` — same shape as today, no downstream changes

The auth service's `/verify` endpoint is no longer called for request auth.
The auth service is **kept** for user + role management (create/delete users, assign roles).

### 2. Dashboard frontend — remove login page

The login page (`/login`) and `authStore` JWT handling become unnecessary.
CF Access intercepts unauthenticated requests and redirects to the IdP login page before they reach the Next.js app.

After CF login, the frontend can call `GET /api/v1/auth/me` (backed by CF JWT) to get the current user's name and role for display purposes.

### 3. CF Access application setup (one-time, in CF dashboard)

Two CF Access Applications:
- `dna-dashboard` → policy: allow specific emails or `@yourcompany.com` domain, OTP email or SSO
- `portal` → **bypass** (no Access enforcement) — CF WAF + DDoS still active, customers use magic links

### 4. Traefik — internal router

Traefik runs as a container in docker-compose. All app containers remove their exposed ports and register via Docker labels. Traefik handles:
- Hostname-based routing to the right container
- Rate limiting on portal `/auth` endpoint (10 req/min per IP)
- Load balancing if containers are scaled (`docker compose scale portal-backend=3`)

```yaml
# Example Traefik label on portal-backend
labels:
  - "traefik.http.routers.portal-api.rule=Host(`portal.yourcompany.com`) && PathPrefix(`/`)"
  - "traefik.http.middlewares.auth-rl.ratelimit.average=10"
  - "traefik.http.middlewares.auth-rl.ratelimit.period=1m"
  - "traefik.http.middlewares.auth-rl.ratelimit.burst=5"
```

### 5. cloudflared tunnel

One `cloudflared` container in docker-compose. Points all hostnames at Traefik (not directly at app containers).
Maps:
- `dna.yourcompany.com` → `traefik:80`
- `portal.yourcompany.com` → `traefik:80`

Traefik then routes by hostname internally. No app ports exposed to the host.

### 6. Role management stays in DB

CF Access tells us **who** the user is (email). It does not know about `admin` / `dna_operator` / `viewer`.
Roles stay in `auth.users`. The dashboard Admin → Users section (already built) is how admins assign roles.

New user provisioning flow:
1. Admin adds user email in dashboard → creates row in `auth.users` with desired role
2. User logs in via CF Access (Google/Azure SSO) → CF JWT contains their email
3. Backend looks up email in `auth.users` → gets role → authorizes request
4. If email not in `auth.users` → 403 (not provisioned)

---

## Dashboard Management UI

A new **Security** tab under Admin → Configuration (alongside the existing Customer Portal tab).

### Sections

**Identity Provider**
- Read-only display: CF team domain (from `CF_TEAM_DOMAIN` env var)
- Auth method: OTP email or SSO (shown from env)
- Link to CF Access dashboard (external)

**User Provisioning**
- Table: email | full name | role | last login | status
- Add user (email + role) — creates `auth.users` row so they can log in after CF auth
- Change role (admin / dna_operator / viewer)
- Deactivate user — sets `is_active = false`; CF still lets them through Access but backend returns 403
- Password reset is gone — users authenticate via CF (OTP or SSO)

**Active Sessions** (optional, phase 2)
- List of `auth.sessions` rows — who is logged in, from where, last seen
- Force-revoke a session

**Access Policy Summary** (read-only)
- Displays `CF_TEAM_DOMAIN`, `CF_APP_AUD` env vars
- Shows whether local dev bypass is enabled (`CF_BYPASS_LOCAL=true`)

**Portal Security** (read-only stats)
- Requests blocked by CF WAF (last 24h) — pulled from CF API or shown as link to CF dashboard
- Rate limit hits on `/auth` endpoint — from Traefik logs/metrics

---

## Local Development

CF Access is not available on `localhost`. Two options:

**Option A — bypass mode (recommended for dev)**
Set `CF_BYPASS_LOCAL=true` in `.env`. The `verify_token` function skips CF JWT check and falls back to `Authorization: Bearer <local-jwt>`. The existing login page and auth service remain functional in dev mode only.

**Option B — CF Tunnel to localhost**
Run `cloudflared tunnel --url http://localhost:3001` — gives a public `*.trycloudflare.com` URL that goes through CF Access. Useful for testing the full flow.

---

## Migration Steps

1. **CF setup** — create team domain, configure OTP email (or connect IdP), create two Access applications (dashboard=enforced, portal=bypass), create tunnel
2. **Traefik** — add `traefik` container to docker-compose; add routing labels to all app containers; remove exposed host ports from app containers
3. **cloudflared** — add `cloudflared` container pointing all hostnames at Traefik
4. **Backend** — update `auth.py` to verify CF JWT; add `CF_TEAM_DOMAIN` + `CF_APP_AUD` + `CF_BYPASS_LOCAL` env vars
5. **Frontend** — remove login page (gate behind `DEV_LOGIN_HELPER` for local dev); add `/api/v1/auth/me` call on app load for user display
6. **DB** — no schema changes; `auth.users` stays as role store; `auth.sessions` kept for audit log
7. **Admin UI** — add Security tab with user provisioning + portal security stats

---

## Files Impacted

| File | Change |
|---|---|
| `dashboard/backend/app/auth.py` | Replace `verify_token` HTTP call with CF JWT verification |
| `dashboard/backend/app/config.py` | Add `CF_TEAM_DOMAIN`, `CF_APP_AUD`, `CF_BYPASS_LOCAL` settings |
| `dashboard/frontend/src/app/login/page.tsx` | Remove (gate behind `DEV_LOGIN_HELPER` for local dev) |
| `dashboard/frontend/src/stores/authStore.ts` | Replace JWT storage with `/me` fetch |
| `docker-compose.yml` | Add `traefik` + `cloudflared` containers; remove exposed host ports from all app containers |
| `traefik/` (new folder) | `traefik.yml` static config + `dynamic/` for route rules |
| `cloudflared/config.yml` (new) | Tunnel ingress rules mapping hostnames → traefik |
| `dashboard/frontend/src/app/admin/page.tsx` | Add Security tab |
| `dashboard/frontend/src/components/admin/SecurityConfig.tsx` | New — user provisioning + portal security stats UI |
| `dashboard/backend/app/routes/security.py` | New — user CRUD for provisioning |

**Unchanged:**
- `auth_service/` — kept for user/role management only
- `customer-portal/` — entirely unchanged (magic-link flow, httpOnly cookie, all endpoints)
- `customer_portal_mcp/` — entirely unchanged
- All other backend routes — `get_current_user` dependency shape unchanged

---

## What We Are NOT Doing

- Not replacing the customer portal magic-link flow
- Not putting customers through CF Access identity gate
- Not removing the `auth.users` table — roles must live somewhere
- Not removing the auth service — it manages users and issues tokens for local dev
- Not using CF Load Balancer — Traefik handles load balancing between container replicas at no extra cost
- Not duplicating rate limiting — Traefik owns `/auth` rate limiting; CF WAF handles volumetric attacks
