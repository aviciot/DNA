"""
DNA Auth Service - User Service
================================
User management operations.
"""

import logging
from typing import Optional, List
from passlib.context import CryptContext

from config.database import get_db_pool
from models.schemas import User

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_user_by_id(user_id: int) -> Optional[User]:
    """
    Get user by ID from database.

    Args:
        user_id: User ID

    Returns:
        User object if found and active, None otherwise
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, email, full_name, role, is_active, created_at, last_login
                FROM auth.users
                WHERE id = $1 AND is_active = true
            """, user_id)

            if row:
                return User(**dict(row))

        return None

    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        return None


async def update_last_login(user_id: int) -> None:
    """
    Update user's last login timestamp.

    Args:
        user_id: User ID
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE auth.users
                SET last_login = NOW()
                WHERE id = $1
            """, user_id)
    except Exception as e:
        logger.error(f"Error updating last login: {e}")


async def get_all_users() -> List[User]:
    """
    Get all users from database.

    Returns:
        List of User objects
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, email, full_name, role, is_active, created_at, last_login
                FROM auth.users
                ORDER BY created_at DESC
            """)

            return [User(**dict(row)) for row in rows]

    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []


async def create_user(email: str, password: str, full_name: str, role: str = "viewer") -> Optional[User]:
    """
    Create a new user.

    Args:
        email: User email
        password: Plain text password
        full_name: User's full name
        role: User role (admin or viewer)

    Returns:
        Created User object or None if failed
    """
    try:
        # Hash password
        hashed_password = pwd_context.hash(password)

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO auth.users (email, password_hash, full_name, role, is_active, created_at)
                VALUES ($1, $2, $3, $4, true, NOW())
                RETURNING id, email, full_name, role, is_active, created_at, last_login
            """, email.lower(), hashed_password, full_name, role)

            if row:
                return User(**dict(row))

        return None

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None


async def delete_user(user_id: int) -> bool:
    """
    Delete a user by ID.

    Args:
        user_id: User ID to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM auth.users
                WHERE id = $1
            """, user_id)

            # Check if any row was deleted
            return result.split()[-1] == "1"

    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return False


async def update_user(user_id: int, email: Optional[str] = None, password: Optional[str] = None, 
                     full_name: Optional[str] = None, role: Optional[str] = None) -> Optional[User]:
    """
    Update a user's information.

    Args:
        user_id: User ID to update
        email: New email (optional)
        password: New password (optional)
        full_name: New full name (optional)
        role: New role (optional)

    Returns:
        Updated User object or None if failed
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Build dynamic update query
            updates = []
            params = []
            param_count = 1
            
            if email is not None:
                updates.append(f"email = ${param_count}")
                params.append(email.lower())
                param_count += 1
            
            if password is not None:
                hashed_password = pwd_context.hash(password)
                updates.append(f"password_hash = ${param_count}")
                params.append(hashed_password)
                param_count += 1
            
            if full_name is not None:
                updates.append(f"full_name = ${param_count}")
                params.append(full_name)
                param_count += 1
            
            if role is not None:
                updates.append(f"role = ${param_count}")
                params.append(role)
                param_count += 1
            
            # If no updates, return current user
            if not updates:
                return await get_user_by_id(user_id)
            
            # Add user_id as last parameter
            params.append(user_id)
            
            query = f"""
                UPDATE auth.users
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, email, full_name, role, is_active, created_at, last_login
            """
            
            row = await conn.fetchrow(query, *params)
            
            if row:
                return User(**dict(row))
            
            return None

    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return None
