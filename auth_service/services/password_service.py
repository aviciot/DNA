"""
DNA Auth Service - Password Service
====================================
Password hashing and verification using bcrypt.
"""

import bcrypt
import logging
from typing import Optional

from config.database import get_db_pool
from models.schemas import User

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.

    Args:
        password: Raw password

    Returns:
        Hashed password (bcrypt hash)
    """
    salt = bcrypt.gensalt(rounds=12)
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    return password_hash.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against bcrypt hash.

    Args:
        password: Raw password
        password_hash: Stored bcrypt password hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


async def get_user_by_email(email: str) -> Optional[User]:
    """
    Get user by email from database.

    Args:
        email: User email

    Returns:
        User object if found and active, None otherwise
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, email, full_name, role, is_active, created_at, last_login
                FROM auth.users
                WHERE email = $1 AND is_active = true
            """, email.lower())

            if row:
                return User(**dict(row))

        return None

    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        return None


async def get_password_hash(user_id: int) -> Optional[str]:
    """
    Get password hash for user.

    Args:
        user_id: User ID

    Returns:
        Password hash if exists, None otherwise
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            password_hash = await conn.fetchval("""
                SELECT password_hash FROM auth.users WHERE id = $1
            """, user_id)

        return password_hash

    except Exception as e:
        logger.error(f"Error getting password hash: {e}")
        return None


async def authenticate_with_password(email: str, password: str) -> Optional[User]:
    """
    Authenticate user with email and password.

    Args:
        email: User email
        password: Raw password

    Returns:
        User object if authentication successful, None otherwise
    """
    try:
        # Get user
        user = await get_user_by_email(email)
        if not user:
            logger.warning(f"Authentication failed: User not found for email {email}")
            return None

        # Get password hash
        password_hash = await get_password_hash(user.id)
        if not password_hash:
            logger.warning(f"Authentication failed: No password hash for user {user.id}")
            return None

        # Verify password
        if not verify_password(password, password_hash):
            logger.warning(f"Authentication failed: Invalid password for user {user.id}")
            return None

        logger.info(f"Authentication successful for user {user.id} ({email})")
        return user

    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        return None
