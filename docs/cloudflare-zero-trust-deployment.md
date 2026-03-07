# Cloudflare Zero Trust — Deployment Guide & Architecture Deep-Dive

---

## Table of Contents

1. [Production Deployment — Step by Step](#1-production-deployment--step-by-step)
2. [Dev Bypass Mode — How It Works](#2-dev-bypass-mode--how-it-works)
3. [How JWT Verification Works Now](#3-how-jwt-verification-works-now)
4. [User Authentication Flow — End to End](#4-user-authentication-flow--end-to-end)
5. [Session Duration — How Long Can a User Stay Logged In](#5-session-duration--how-long-can-a-user-stay-logged-in)
6. [Security Edge Cases](#6-security-edge-cases)

---

## 1. Production Deployment — Step by Step

### Prerequisites

- A Cloudflare account (free tier works for Access)
- A domain managed by Cloudflare DNS (e.g. `yourcompany.com`)
- Docker + Docker Compose on your server
- The repo checked out on the server

---

### Step 1 — Create a Cloudflare Team Domain

1. Go to [one.dash.cloudflare.com](https://one.dash.cloudflare.com)
2. Click **Settings → General**
3. Set your **Team Domain** — e.g. `yourteam.cloudflareaccess.com`
   - This becomes `CF_TEAM_DOMAIN` in your `.env`
   - It is the domain used for the login page and JWKS endpoint

---

### Step 2 — Configure the Identity Provider (IdP)

Go to **Settings → Authentication → Login Methods**

Choose one:

| Option | When to use |
|---|---|
| **One-time PIN (OTP)** | Simple email-based login, no external IdP needed |
| **Google Workspace** | If your team uses Gmail / Google accounts |
| **Azure AD / Entra ID** | If your company uses Microsoft 365 |
| **Okta / JumpCloud** | Dedicated IAM provider |

For OTP (simplest, no setup):
- Click **Add → One-time PIN**
- Enable it — done. Users get a 6-digit code emailed to them on login.

---

### Step 3 — Create the Dashboard Access Application

1. Go to **Access → Applications → Add an Application**
2. Choose **Self-hosted**
3. Fill in:
   - **Name:** `DNA Dashboard`
   - **Subdomain:** `dna` (creates `dna.yourcompany.com`)
   - **Domain:** `yourcompany.com`
4. Under **Policies** → Add a policy:
   - **Action:** Allow
   - **Rule:** Emails ending in `@yourcompany.com`
   - Or add specific email addresses for granular control
5. Under **Settings → CORS** — enable if the frontend makes cross-origin API calls
6. Click **Save**
7. On the application detail page, copy the **Application Audience (AUD) tag** — a 64-char hex string
   - This becomes `CF_APP_AUD` in your `.env`

---

### Step 4 — Create the Portal Access Application (Bypass Mode)

1. Go to **Access → Applications → Add an Application**
2. Choose **Self-hosted**
3. Fill in:
   - **Name:** `Customer Portal`
   - **Subdomain:** `portal` (creates `portal.yourcompany.com`)
   - **Domain:** `yourcompany.com`
4. Under **Policies** → Add a policy:
   - **Action:** Bypass
   - **Rule:** Everyone
   - This means CF Access does NOT gate the portal — customers access it freely
5. CF WAF + DDoS protection is still active (the tunnel is still used)
6. Click **Save**

> **Why bypass?** Customers don't have company accounts. They authenticate via magic links
> stored in your database. CF protects the infrastructure but does not touch auth logic.

---

### Step 5 — Create a Cloudflare Tunnel

1. Go to **Networks → Tunnels → Create a Tunnel**
2. Choose **Cloudflared**
3. Name it: `dna-production`
4. Copy the **Tunnel Token** shown — this becomes `CF_TUNNEL_TOKEN` in your `.env`
5. Under **Public Hostnames**, add two routes:

   | Subdomain | Domain | Service |
   |---|---|---|
   | `dna` | `yourcompany.com` | `http://traefik:80` |
   | `portal` | `yourcompany.com` | `http://traefik:80` |

   > Both hostnames point at Traefik. Traefik routes by `Host` header internally.

6. Save the tunnel — it does not need to be running yet.

---

### Step 6 — Set Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# ---- Cloudflare ----
CF_BYPASS_LOCAL=false                          # MUST be false in production
CF_TEAM_DOMAIN=yourteam.cloudflareaccess.com  # from Step 1
CF_APP_AUD=abc123...64chars                    # from Step 3 (dashboard app AUD)
CF_TUNNEL_TOKEN=eyJ...                         # from Step 5
CF_DNA_HOSTNAME=dna.yourcompany.com
CF_PORTAL_HOSTNAME=portal.yourcompany.com

# ---- Internal service token ----
# Generate with: openssl rand -hex 32
CF_INTERNAL_SERVICE_TOKEN=a9f3...64chars

# ---- Frontend ----
NEXT_PUBLIC_CF_BYPASS=false                    # disables login form in production
NEXT_PUBLIC_CF_TEAM_DOMAIN=yourteam.cloudflareaccess.com

# ---- Security keys ----
SECRET_KEY=<random-64-chars>
JWT_SECRET_KEY=<random-64-chars>

# ---- DB / Redis ----
# (leave internal, do NOT expose ports to the internet)
```

> **Never commit `.env` to git.** Use `.env.example` as the template.

---

### Step 7 — Deploy

```bash
# On your server
git pull origin feature/cloudflare-zero-trust

# Build and start all services
docker compose up -d --build

# Verify all containers are running
docker compose ps

# Verify Traefik is routing
curl -H "Host: dna.yourcompany.com" http://localhost/health

# Verify cloudflared is connected
docker compose logs cloudflared
# Should show: "Registered tunnel connection"
```

---

### Step 8 — Provision the First Admin User

Before any staff member can log in, their email must exist in `auth.users`.

```bash
# Connect to the running backend container
docker compose exec dna-backend python -c "
import asyncio
from app.database import get_db_pool

async def seed():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO auth.users (email, full_name, role, is_active, password_hash)
               VALUES (\$1, \$2, \$3, true, \'\')
               ON CONFLICT (email) DO NOTHING''',
            'yourname@yourcompany.com', 'Your Name', 'admin'
        )
    print('Done')

asyncio.run(seed())
"
```

After this, that user can:
1. Navigate to `https://dna.yourcompany.com`
2. CF Access intercepts → redirects to CF login page
3. They authenticate via OTP/SSO
4. CF redirects back to the dashboard
5. Dashboard calls `/api/v1/auth/me` → gets their role → they are in

All subsequent user provisioning is done via the **Admin → Configuration → Security** tab.

---

### Step 9 — Verify the Full Flow

```bash
# 1. Unauthenticated request to dashboard should redirect to CF login
curl -I https://dna.yourcompany.com
# Expected: 302 → https://yourteam.cloudflareaccess.com/...

# 2. Portal should be accessible without auth (bypass mode)
curl -I https://portal.yourcompany.com
# Expected: 200

# 3. API without CF JWT should return 401
curl https://dna.yourcompany.com/api/v1/dashboard/stats
# Expected: 401 Unauthorized

# 4. Check cloudflared tunnel status in CF dashboard
# Networks → Tunnels → dna-production → should show "Healthy"
```

---

## 2. Dev Bypass Mode — How It Works

### Yes, you can fully bypass CF when developing locally.

Set in your local `.env`:

```bash
CF_BYPASS_LOCAL=true
NEXT_PUBLIC_CF_BYPASS=true
NEXT_PUBLIC_DEV_LOGIN_HELPER=true
```

With these flags:

| What happens | Dev (bypass=true) | Production (bypass=false) |
|---|---|---|
| Login page | Full email + password form | CF redirects before page loads |
| Token storage | `localStorage` (access + refresh tokens) | None — CF session cookie only |
| API auth header | `Authorization: Bearer <jwt>` | Not sent — CF header injected by edge |
| Backend auth check | Calls `dna-auth:3011/verify` | Verifies `Cf-Access-Jwt-Assertion` header |
| JWT secret | Your `JWT_SECRET_KEY` (HS256) | CF's RSA private key (RS256) |
| JWKS fetch | Never called | Called on first request, cached 1 hour |

### How the bypass works in the backend

`auth.py` checks `settings.CF_BYPASS_LOCAL` at the top of `get_current_user`:

```
Request arrives at FastAPI
       |
       ├─ Is Cf-Access-Jwt-Assertion header present AND CF_BYPASS_LOCAL=false?
       │         YES → verify CF JWT (production path)
       │
       ├─ Is X-Internal-Service-Token header present?
       │         YES → verify against CF_INTERNAL_SERVICE_TOKEN (service accounts)
       │
       └─ Is Authorization: Bearer present AND CF_BYPASS_LOCAL=true?
                 YES → call dna-auth:3011/verify (dev path)
                 NO  → 401 Unauthorized
```

### What still runs in dev that does NOT run in production

| Component | Dev | Prod |
|---|---|---|
| `dna-auth` service | Running (issues + verifies JWTs) | Running (user management only) |
| Login page | Shown | Never reached (CF gates before it) |
| `localStorage` tokens | Used | Not used |
| `traefik` | Runs but routes localhost | Routes all CF tunnel traffic |
| `cloudflared` | Optional (can run `cloudflared tunnel --url http://localhost:3001` for full CF test) | Required |

### Testing the full CF flow locally (Option B)

If you want to test CF Access locally without deploying to a server:

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# Expose localhost to the internet with a temporary Cloudflare URL
cloudflared tunnel --url http://localhost:3001

# Output: https://random-name.trycloudflare.com
# You can point a CF Access application at this URL for testing
```

---

## 3. How JWT Verification Works Now

### Old flow (before migration)

```
Browser → dna-backend → [HTTP call] → dna-auth:3011/verify → returns headers
                                            ↑
                               Network hop on EVERY request
                               (adds ~2-5ms per request)
                               Single point of failure
```

### New flow (after migration)

```
Browser → [CF Edge validates session] → dna-backend
                                              ↓
                               Reads Cf-Access-Jwt-Assertion header
                               Verifies RS256 signature locally
                               (no network hop, ~0.1ms)
```

---

### The CF JWT itself

When a user authenticates through CF Access, Cloudflare issues a **signed JWT** (JSON Web Token).

On every subsequent request, CF injects this JWT into the request header:

```
Cf-Access-Jwt-Assertion: eyJhbGciOiJSUzI1NiIsImtpZCI6Ii4uLiJ9.eyJzdWIiOiI...
```

The JWT contains:

```json
{
  "aud": ["abc123...your-app-aud"],
  "email": "user@yourcompany.com",
  "exp": 1741234567,
  "iat": 1741230967,
  "iss": "https://yourteam.cloudflareaccess.com",
  "sub": "cf-unique-user-id",
  "type": "app",
  "identity_nonce": "..."
}
```

The backend uses the `email` claim to look up the user in `auth.users` and get their `role`.

---

### JWKS Caching — Does it cache all users?

**No. The cache stores Cloudflare's public signing keys, NOT user data.**

Here is exactly what is cached:

```
Redis key: "cf:jwks"
TTL:       3600 seconds (1 hour)
Contents:  Cloudflare's RSA public keys (JWKS format)

Example:
{
  "keys": [
    {
      "kid": "abc123",
      "kty": "RSA",
      "alg": "RS256",
      "n": "...large-number...",
      "e": "AQAB"
    }
  ]
}
```

This is **Cloudflare's public key**, used to verify the signature on every JWT.
It is the same key for all users — not user-specific.

**Per-request flow:**

```
Request with Cf-Access-Jwt-Assertion header
           |
           ├─ GET "cf:jwks" from Redis   ← shared cache, ~0.1ms
           │        |
           │   (miss) → fetch from https://yourteam.cloudflareaccess.com/cdn-cgi/access/certs
           │           → store in Redis for 1 hour
           │           → store in process memory as fallback
           |
           ├─ Verify JWT signature with public key (RS256, local CPU operation)
           |
           ├─ Extract email from JWT payload
           |
           ├─ Check Redis revocation set: SISMEMBER "cf:revoked" <email>
           |        → if member: 403 Account deactivated (instant effect)
           |
           └─ SELECT from auth.users WHERE email = ?   ← DB query (gets role)
                    → 403 if not found or is_active=false
                    → return {user_id, email, full_name, role}
```

**Summary of what lives in cache:**

| Cache key | What it is | TTL | Per-user? |
|---|---|---|---|
| `cf:jwks` | CF's RSA public keys | 1 hour | No — one entry for all users |
| `cf:revoked` | SET of deactivated emails | 15 min | Yes — one entry per deactivated user |

There is **no user session cache**. Every request hits the DB for the role lookup.
This is by design — role changes take effect on the next request with no cache lag.

If you want to add a user-level cache for performance at scale, add:
```python
# redis key: "cf:user:{email}" → {"user_id": ..., "role": ...}  TTL: 5 min
```
This is a future optimization — the current setup is correct for the system size.

---

### Key rotation handling

CF rotates their signing keys periodically (without notice).
The code handles this automatically:

```
jwt.decode() raises JWTError (signature invalid)
       |
       ├─ Invalidate Redis "cf:jwks" + in-memory cache
       |
       ├─ Re-fetch JWKS from CF endpoint
       |
       └─ Retry jwt.decode() with fresh keys
                → success: continue
                → still fails: return 401 (genuine bad token)
```

This means a key rotation causes at most **one extra HTTP request to CF per backend process**,
and then the new keys are cached for the next hour.

---

## 4. User Authentication Flow — End to End

### First-time login (production)

```
1. User navigates to https://dna.yourcompany.com/
   │
2. CF Edge checks: does this request have a valid CF Access session cookie?
   │    NO
   │
3. CF redirects to: https://yourteam.cloudflareaccess.com/
   │    User sees CF login page (OTP email / Google / Azure)
   │
4. User enters email → CF sends 6-digit OTP code to that email
   │
5. User enters OTP code → CF validates
   │    CF checks: is this email allowed by the Access policy?
   │    (e.g. must end with @yourcompany.com)
   │
6. CF creates a session for the user and issues two things:
   ├── A session cookie (httpOnly, CF-managed): CF_Authorization=...
   └── A signed JWT: the Cf-Access-Jwt-Assertion
   │
7. CF redirects the browser back to https://dna.yourcompany.com/
   │    The CF_Authorization session cookie is now stored in browser
   │
8. Browser loads the Next.js app
   │
9. Next.js app calls GET /api/v1/auth/me
   │    Request goes: Browser → CF Edge → cloudflared → Traefik → dna-backend
   │    CF Edge injects "Cf-Access-Jwt-Assertion: eyJ..." header
   │
10. dna-backend.auth.get_current_user() reads the header
    │    Verifies JWT signature against CF public keys (from Redis/memory cache)
    │    Extracts email: user@yourcompany.com
    │    Checks revocation set: not revoked
    │    SELECT from auth.users WHERE email = 'user@yourcompany.com'
    │    Returns: {user_id: 7, email: "...", full_name: "Jane", role: "dna_operator"}
    │
11. /me returns user object to frontend
    │
12. authStore sets: { user: {...}, isAuthenticated: true }
    │
13. User sees the dashboard — done
```

### Subsequent requests (same session)

```
User clicks something in the dashboard
       |
Browser sends request to https://dna.yourcompany.com/api/v1/...
       |   (automatically includes CF_Authorization session cookie)
       |
CF Edge validates the session cookie
       |   (fast — CF edge validation, no round-trip to your server)
       |
CF injects Cf-Access-Jwt-Assertion header (same JWT, valid for ~15 min)
       |
Traefik routes to dna-backend
       |
Backend verifies JWT (local RS256 check, ~0.1ms)
       |
Backend queries DB for role (single indexed SELECT, ~1ms)
       |
Request is processed and response returned
```

No login prompt. No token refresh. No localStorage. It just works transparently.

---

### What the frontend stores

In **production mode** (`CF_BYPASS=false`):

```
localStorage: nothing auth-related
sessionStorage: nothing
Cookies: CF_Authorization (httpOnly, set by CF edge, invisible to JavaScript)
```

The session cookie is `httpOnly` and `SameSite=Lax` — JavaScript cannot read it.
This eliminates the entire class of XSS token theft vulnerabilities.

In **dev mode** (`CF_BYPASS=true`):

```
localStorage:
  access_token: eyJhbGci...   (HS256 JWT, 30-min TTL, issued by dna-auth)
  refresh_token: eyJhbGci... (HS256 JWT, 7-day TTL, issued by dna-auth)
```

---

## 5. Session Duration — How Long Can a User Stay Logged In

There are two separate concepts here: the **CF session** and the **CF JWT**.
They have different lifetimes and work together.

---

### The CF Access Session (the session cookie)

| Property | Value |
|---|---|
| What it is | A session cookie (`CF_Authorization`) managed entirely by Cloudflare |
| Default TTL | **24 hours** (configurable in CF Access application settings) |
| Where stored | Browser cookie — httpOnly, invisible to JavaScript |
| What it does | Proves to the CF edge that the user already authenticated |
| Renewal | Automatically renewed on activity (sliding window) |

**How to change session duration:**
In CF Access → your application → Settings → Session Duration
Options: 15m, 30m, 1h, 6h, 12h, **24h** (default), 7d, 30d, no expiry

With the default 24h: a user who logs in at 9am can keep using the dashboard until 9am the next day without re-authenticating (or longer with sliding window renewal).

---

### The CF Access JWT (the Cf-Access-Jwt-Assertion header)

| Property | Value |
|---|---|
| What it is | A short-lived RS256 JWT injected by the CF edge on each request |
| TTL | **~15 minutes** (fixed by Cloudflare, not configurable) |
| Where it lives | Request header only — never stored by the browser |
| What it does | Proves to your backend that the request came through CF Access |

**This is not the same as the session.** The session cookie can be valid for 24h,
but the JWT injected into each request is always a fresh 15-minute token.

```
Timeline:
  t=0:00  User logs in → CF creates session (24h TTL), injects JWT #1 (exp: t=0:15)
  t=0:10  User makes request → CF validates session (still valid) → injects JWT #2 (exp: t=0:25)
  t=0:30  User makes request → CF validates session (still valid) → injects JWT #3 (exp: t=0:45)
  t=24:00 Session expires → user is redirected to CF login page
  t=24:05 User re-authenticates via OTP → new 24h session starts
```

**From the user's perspective:** they stay "logged in" for 24 hours (or configured duration).
They never see the JWT — it is infrastructure.

---

### The revocation gap and how we handle it

Because CF JWTs last ~15 minutes, there is a window where a deactivated user's JWT
is still technically valid even after you mark them as inactive in the DB.

**Worst case without mitigation:**
Admin deactivates user at t=0. User's current JWT expires at t=7 (7 minutes left).
For 7 minutes, the user can still make API calls.

**Our mitigation — Redis revocation set:**

When an admin calls `PATCH /api/v1/security/users/{id}/deactivate`:
1. Sets `is_active=false` in DB → immediate for new requests that hit the DB
2. Calls `revoke_user(email)`:
   ```python
   await redis_client.sadd("cf:revoked", email)
   await redis_client.expire("cf:revoked", 900)  # 15 min TTL
   ```
3. Every subsequent request checks `SISMEMBER cf:revoked <email>` before the DB query
4. Returns 403 immediately — **effect is instant**, no waiting for JWT to expire

```
Timeline with revocation:
  t=0:00  User logs in, gets CF session
  t=0:10  Admin deactivates user → DB updated + Redis revocation set updated
  t=0:10  User makes next request → JWT still valid (signed by CF)
                                  → SISMEMBER cf:revoked "user@..." → TRUE
                                  → 403 Forbidden (instant)
```

**The revocation set TTL is 15 minutes** — after that, the entry expires, but by then
the user's JWT has also expired, so they'd need a new session to proceed (and the
`is_active=false` DB check would catch them anyway).

---

### Summary table

| Token / Session | TTL | Where stored | Who manages it | Revocable? |
|---|---|---|---|---|
| CF session cookie | 24h (configurable) | Browser (httpOnly) | Cloudflare | Yes — via CF Access dashboard, or deactivate in our DB |
| CF Access JWT | ~15 min | Request header only | Cloudflare | Effectively yes — Redis revocation set blocks within milliseconds |
| Dev access token | 30 min | localStorage | dna-auth service | Yes — delete from DB or localStorage |
| Dev refresh token | 7 days | localStorage | dna-auth service | Yes — delete from DB |

---

## 6. Security Edge Cases

### What if Redis is down?

`_is_revoked()` wraps the Redis call in `try/except` and **returns False on failure**
(fail open). This means:
- If Redis is down, revocation checks are skipped
- The DB `is_active` check still runs on every request
- Worst case: a deactivated user gets up to 15 min of access

This is the correct tradeoff — a Redis outage should not lock out all users.
If you need hard revocation guarantees regardless of Redis, set the DB `is_active=false`
AND revoke the CF session from the CF Access dashboard.

### What if someone sends a forged Cf-Access-Jwt-Assertion header?

The header is verified using RS256 (asymmetric cryptography). Without Cloudflare's
private key, it is computationally infeasible to forge a valid signature.

The JWKS endpoint returns CF's **public keys** only. The private key never leaves CF's
infrastructure.

Even if `CF_BYPASS_LOCAL=false` and someone sends a self-signed RS256 token, the
`kid` (key ID) in the token header must match one of CF's known public keys.
It won't — so `jwt.decode()` raises `JWTError` → 401.

### What if CF is down?

Requests arrive from users → CF edge is unavailable → users cannot reach the tunnel.

This is a deliberate tradeoff: CF is the security boundary. If CF is down, the
application is not reachable — but it is also completely safe (no open ports).

For high availability, CF's network has 300+ data centers and 99.9%+ uptime SLA.

### Can a staff user access the portal as a customer?

No. The portal uses a separate auth mechanism (magic link token + httpOnly cookie).
CF Access does not gate the portal. Portal endpoints verify the `portal_token` cookie
against the `customer_portal_access` table — completely separate from `auth.users`.

### What about the WebSocket endpoints?

WebSocket connections go through CF Tunnel as HTTP Upgrade requests.
CF Access validates the session on the initial HTTP Upgrade.
The `Cf-Access-Jwt-Assertion` header is present on the upgrade request.

Our WebSocket endpoints use `verify_token(token)` with a query param (`?token=...`).
In dev bypass mode, this is a short-lived HS256 JWT from the auth service.
In production, the WebSocket client should pass the CF JWT as the query param
(the frontend can read it from... actually it cannot — it's a header, not accessible to JS).

**Production WebSocket recommendation:** Update the WebSocket handler to read
`websocket.headers.get("Cf-Access-Jwt-Assertion")` instead of a query param.
This is a follow-up task for Phase 2 — current behavior works in dev bypass mode.
