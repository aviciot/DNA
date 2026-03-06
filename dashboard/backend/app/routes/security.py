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


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROLES = {"admin", "dna_operator", "viewer"}


def _check_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")


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
    """Provision a new user (creates auth.users row so CF-authenticated user can log in)."""
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
    logger.info(f"Provisioned user {body.email} with role {body.role} by {admin['email']}")
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
    # Add to Redis revocation set for immediate effect (before CF JWT expires)
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
    await revoke_user(row["email"])
    logger.info(f"Deleted user {row['email']} by {admin['email']}")
    return {"deleted": True, "id": row["id"]}
