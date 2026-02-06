"""
DNA Auth Service - Token Service
=================================
JWT token operations (create, verify, revoke).
"""

import logging
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from jose import jwt, JWTError
from fastapi import HTTPException

from config.settings import settings
from config.database import get_db_pool
from models.schemas import User

logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    """Create SHA256 hash of token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_access_token(user: User) -> str:
    """
    Create JWT access token.

    Args:
        user: User object

    Returns:
        JWT access token string
    """
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    # Store session in database
    try:
        pool = await get_db_pool()
        session_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO auth.sessions (session_id, user_id, access_token, expires_at)
                VALUES ($1, $2, $3, $4)
            """, session_id, user.id, hash_token(token), expire)
    except Exception as e:
        logger.warning(f"Failed to store session: {e}")

    return token


async def create_refresh_token(user: User) -> str:
    """
    Create JWT refresh token.

    Args:
        user: User object

    Returns:
        JWT refresh token string
    """
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user.id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    # Update most recent session with refresh token
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE auth.sessions
                SET refresh_token = $1
                WHERE user_id = $2 AND expires_at > NOW()
                AND id = (
                    SELECT id FROM auth.sessions
                    WHERE user_id = $2 AND expires_at > NOW()
                    ORDER BY created_at DESC LIMIT 1
                )
            """, hash_token(token), user.id)
    except Exception as e:
        logger.warning(f"Failed to update refresh token: {e}")

    return token


async def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token.

    Args:
        token: JWT token string

    Returns:
        Token payload dict

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Decode token
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Check if session still exists
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            session_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM auth.sessions
                    WHERE (access_token = $1 OR refresh_token = $1)
                    AND expires_at > NOW()
                )
            """, hash_token(token))

            if not session_exists:
                raise HTTPException(401, "Session expired or invalid")

        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(401, "Invalid or expired token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(401, "Token verification failed")


async def revoke_token(token: str) -> None:
    """
    Revoke (delete) a token session.

    Args:
        token: JWT token string to revoke
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM auth.sessions
                WHERE access_token = $1 OR refresh_token = $1
            """, hash_token(token))

        logger.info("Token session revoked")

    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        raise
