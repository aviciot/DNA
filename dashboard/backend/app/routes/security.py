"""
DNA Backend - Security Routes
==============================
User provisioning and CF Zero Trust configuration management.
Admin-only endpoints.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from ..auth import require_admin, revoke_user
from ..database import get_db_pool
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/security", tags=["Security"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str  # admin | dna_operator | viewer


class UserRoleUpdate(BaseModel):
    role: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]


class ActivityEntry(BaseModel):
    id: int
    user_email: Optional[str]
    action: str
    target_email: Optional[str]
    detail: Optional[str]
    ip_address: Optional[str]
    performed_by_email: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROLES = {"admin", "dna_operator", "viewer"}


def _check_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")


async def _log(conn, *, actor_id: int, action: str, target_id: int = None, detail: str = None):
    await conn.execute(
        """
        INSERT INTO auth.user_activity_log (user_id, action, target_id, detail, performed_by)
        VALUES ($1, $2, $3, $4, $5)
        """,
        actor_id, action, target_id, detail, actor_id,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/info")
async def get_security_info(admin=Depends(require_admin)):
    """Return CF Zero Trust configuration info (read-only, no secrets)."""
    return {
        "cf_team_domain": settings.CF_TEAM_DOMAIN or None,
        "cf_app_aud_configured": bool(settings.CF_APP_AUD),
        "bypass_mode": settings.CF_BYPASS_LOCAL,
        "auth_method": "local-dev-bypass" if settings.CF_BYPASS_LOCAL else "cloudflare-access",
        "cf_dashboard_url": (
            f"https://one.dash.cloudflare.com" if settings.CF_TEAM_DOMAIN else None
        ),
    }


@router.get("/users", response_model=List[UserOut])
async def list_users(admin=Depends(require_admin)):
    """List all provisioned users."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, email, full_name, role, is_active, created_at, last_login
            FROM auth.users
            ORDER BY created_at DESC
            """
        )
    return [dict(r) for r in rows]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, admin=Depends(require_admin)):
    """Provision a new user."""
    _check_role(body.role)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM auth.users WHERE email = $1", body.email
        )
        if existing:
            raise HTTPException(409, "User with this email already exists")
        row = await conn.fetchrow(
            """
            INSERT INTO auth.users (email, full_name, role, is_active, password_hash)
            VALUES ($1, $2, $3, true, '')
            RETURNING id, email, full_name, role, is_active, created_at, last_login
            """,
            body.email, body.full_name, body.role,
        )
        await _log(conn, actor_id=admin["user_id"], action="provision",
                   target_id=row["id"], detail=f"role={body.role}")
    logger.info(f"Provisioned user {body.email} with role {body.role} by {admin['email']}")
    return dict(row)


@router.patch("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, admin=Depends(require_admin)):
    """Update user full_name and/or email."""
    if not body.full_name and not body.email:
        raise HTTPException(400, "Nothing to update")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE auth.users
            SET
                full_name = COALESCE($1, full_name),
                email     = COALESCE($2, email)
            WHERE id = $3
            RETURNING id, email, full_name, role, is_active, created_at, last_login
            """,
            body.full_name, str(body.email) if body.email else None, user_id,
        )
        if not row:
            raise HTTPException(404, "User not found")
        await _log(conn, actor_id=admin["user_id"], action="update_profile", target_id=user_id)
    logger.info(f"Updated user {row['email']} profile by {admin['email']}")
    return dict(row)


@router.patch("/users/{user_id}/role")
async def update_user_role(user_id: int, body: UserRoleUpdate, admin=Depends(require_admin)):
    """Change a user role."""
    _check_role(body.role)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE auth.users SET role = $1
            WHERE id = $2
            RETURNING id, email, role
            """,
            body.role, user_id,
        )
        if not row:
            raise HTTPException(404, "User not found")
        await _log(conn, actor_id=admin["user_id"], action="role_change",
                   target_id=user_id, detail=f"role={body.role}")
    logger.info(f"Updated user {row['email']} role to {body.role} by {admin['email']}")
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(user_id: int, admin=Depends(require_admin)):
    """Deactivate a user (blocks backend access immediately via revocation set)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE auth.users SET is_active = false
            WHERE id = $1
            RETURNING id, email
            """,
            user_id,
        )
        if not row:
            raise HTTPException(404, "User not found")
        await _log(conn, actor_id=admin["user_id"], action="deactivate", target_id=user_id)
    await revoke_user(row["email"])
    logger.info(f"Deactivated user {row['email']} by {admin['email']}")
    return {"id": row["id"], "email": row["email"], "is_active": False}


@router.patch("/users/{user_id}/activate")
async def activate_user(user_id: int, admin=Depends(require_admin)):
    """Reactivate a previously deactivated user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE auth.users SET is_active = true
            WHERE id = $1
            RETURNING id, email
            """,
            user_id,
        )
        if not row:
            raise HTTPException(404, "User not found")
        await _log(conn, actor_id=admin["user_id"], action="activate", target_id=user_id)
    logger.info(f"Reactivated user {row['email']} by {admin['email']}")
    return {"id": row["id"], "email": row["email"], "is_active": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin=Depends(require_admin)):
    """Permanently delete a user record."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM auth.users WHERE id = $1 RETURNING id, email",
            user_id,
        )
        if not row:
            raise HTTPException(404, "User not found")
        await _log(conn, actor_id=admin["user_id"], action="delete",
                   target_id=row["id"], detail=row["email"])
    await revoke_user(row["email"])
    logger.info(f"Deleted user {row['email']} by {admin['email']}")
    return {"deleted": True, "id": row["id"]}


@router.get("/activity", response_model=List[ActivityEntry])
async def get_activity_log(limit: int = 100, admin=Depends(require_admin)):
    """Return recent user activity log entries."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                l.id,
                u.email        AS user_email,
                l.action,
                t.email        AS target_email,
                l.detail,
                l.ip_address::text,
                p.email        AS performed_by_email,
                l.created_at
            FROM auth.user_activity_log l
            LEFT JOIN auth.users u ON l.user_id     = u.id
            LEFT JOIN auth.users t ON l.target_id   = t.id
            LEFT JOIN auth.users p ON l.performed_by = p.id
            ORDER BY l.created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]
