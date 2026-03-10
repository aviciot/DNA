"""
DNA Backend - Authentication Middleware
========================================
Cloudflare Zero Trust JWT verification.

Priority order for request authentication:
  1. Cf-Access-Jwt-Assertion header  -- production (CF edge validates before forwarding)
  2. X-Internal-Service-Token header -- inter-container service accounts
  3. Authorization: Bearer <jwt>     -- local dev bypass (CF_BYPASS_LOCAL=true only)
"""

import json
import logging
import time
from typing import Optional

import httpx
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from .config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

_jwks_memory = None
_jwks_memory_time = 0.0
JWKS_CACHE_TTL = 3600
REVOCATION_KEY = "cf:revoked"


async def _get_jwks() -> dict:
    global _jwks_memory, _jwks_memory_time

    try:
        from .redis_client import redis_client
        cached = await redis_client.get("cf:jwks")
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    if _jwks_memory and (time.time() - _jwks_memory_time) < JWKS_CACHE_TTL:
        return _jwks_memory

    url = f"https://{settings.CF_TEAM_DOMAIN}/cdn-cgi/access/certs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        jwks = resp.json()

    try:
        from .redis_client import redis_client
        await redis_client.setex("cf:jwks", JWKS_CACHE_TTL, json.dumps(jwks))
    except Exception:
        pass

    _jwks_memory = jwks
    _jwks_memory_time = time.time()
    return jwks


async def _invalidate_jwks_cache() -> None:
    global _jwks_memory, _jwks_memory_time
    _jwks_memory = None
    _jwks_memory_time = 0.0
    try:
        from .redis_client import redis_client
        await redis_client.delete("cf:jwks")
    except Exception:
        pass


async def _decode_cf_jwt(token: str) -> dict:
    jwks = await _get_jwks()
    try:
        return jwt.decode(token, jwks, algorithms=["RS256"], audience=settings.CF_APP_AUD)
    except JWTError:
        await _invalidate_jwks_cache()
        try:
            jwks = await _get_jwks()
            return jwt.decode(token, jwks, algorithms=["RS256"], audience=settings.CF_APP_AUD)
        except JWTError as exc:
            logger.warning(f"CF JWT verification failed: {exc}")
            raise HTTPException(401, "Invalid Cloudflare Access token")


async def _user_from_db(email: str, request: Request = None) -> dict:
    from .database import get_db_pool
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, full_name, role, is_active FROM auth.users WHERE email = $1",
            email,
        )
        if not row:
            raise HTTPException(403, "User not provisioned -- contact your administrator")
        if not row["is_active"]:
            raise HTTPException(403, "Account deactivated")
        ip = request.client.host if request else None
        ua = request.headers.get("user-agent") if request else None
        await conn.execute(
            """
            UPDATE auth.users SET last_login = NOW()
            WHERE id = $1
              AND (last_login IS NULL OR last_login < NOW() - INTERVAL '5 minutes')
            """,
            row["id"],
        )
        await conn.execute(
            """
            INSERT INTO auth.user_activity_log (user_id, action, ip_address, user_agent)
            SELECT $1, 'login', $2, $3
            WHERE NOT EXISTS (
                SELECT 1 FROM auth.user_activity_log
                WHERE user_id = $1 AND action = 'login'
                  AND created_at > NOW() - INTERVAL '5 minutes'
            )
            """,
            row["id"], ip, ua,
        )
    return {
        "user_id": row["id"],
        "email": row["email"],
        "full_name": row.get("full_name") or "",
        "role": row["role"],
    }


async def _is_revoked(email: str) -> bool:
    try:
        from .redis_client import redis_client
        return bool(await redis_client.sismember(REVOCATION_KEY, email))
    except Exception:
        return False


async def revoke_user(email: str) -> None:
    try:
        from .redis_client import redis_client
        await redis_client.sadd(REVOCATION_KEY, email)
        await redis_client.expire(REVOCATION_KEY, 900)
    except Exception:
        pass


async def _verify_cf_path(cf_jwt: str, request: Request = None) -> dict:
    payload = await _decode_cf_jwt(cf_jwt)
    email = payload.get("email")
    if not email:
        raise HTTPException(401, "No email claim in CF Access token")
    if await _is_revoked(email):
        raise HTTPException(403, "Account deactivated")
    return await _user_from_db(email, request)


async def verify_token(token: str, request: Request = None) -> dict:
    if not settings.CF_BYPASS_LOCAL:
        return await _verify_cf_path(token, request)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if response.status_code == 200:
                user = {
                    "user_id": int(response.headers.get("X-User-Id", 0)),
                    "email": response.headers.get("X-User-Email", ""),
                    "full_name": "",
                    "role": response.headers.get("X-User-Role", "viewer"),
                }
                # still update last_login for bypass mode
                await _user_from_db(user["email"], request)
                return user
            raise HTTPException(401, "Invalid token")
    except httpx.RequestError as exc:
        logger.error(f"Auth service connection error: {exc}")
        raise HTTPException(503, "Authentication service unavailable")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    cf_jwt = request.headers.get("Cf-Access-Jwt-Assertion")
    if cf_jwt and not settings.CF_BYPASS_LOCAL:
        return await _verify_cf_path(cf_jwt, request)

    internal_token = request.headers.get("X-Internal-Service-Token")
    if internal_token and settings.CF_INTERNAL_SERVICE_TOKEN:
        if internal_token == settings.CF_INTERNAL_SERVICE_TOKEN:
            return {"user_id": 0, "email": "service@internal", "full_name": "Service Account", "role": "admin"}
        raise HTTPException(401, "Invalid internal service token")

    if not credentials:
        raise HTTPException(401, "Authorization required")

    if not settings.CF_BYPASS_LOCAL:
        raise HTTPException(401, "Cloudflare Access token required")

    return await verify_token(credentials.credentials, request)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user


async def require_operator(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("admin", "dna_operator"):
        raise HTTPException(403, "Operator or admin access required")
    return user
