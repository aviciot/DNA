"""
DNA Auth Service - User Routes
===============================
User profile and management endpoints.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.database import get_db_pool
from models.schemas import UserResponse, CreateUserRequest, UserListResponse, UpdateUserRequest
from services.token_service import verify_token
from services.user_service import get_user_by_id, get_all_users, create_user, delete_user, update_user

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)


async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to get current user from token.
    
    Args:
        credentials: Bearer token from Authorization header
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        payload = await verify_token(credentials.credentials)
        user_id = int(payload.get("sub"))
        user = await get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(401, "Invalid authentication credentials")


async def require_admin(user = Depends(get_current_user_from_token)):
    """
    Dependency to require admin role.
    
    Args:
        user: Current user
        
    Returns:
        User object if admin
        
    Raises:
        HTTPException: If user is not admin
    """
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return user



@router.get("/me", response_model=UserResponse)
async def get_current_user(user = Depends(get_current_user_from_token)):
    """
    Get current user information from JWT token.
    
    Args:
        user: Current authenticated user
        
    Returns:
        Current user information
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login
    )


@router.get("", response_model=List[UserListResponse])
async def list_users(admin = Depends(require_admin)):
    """
    List all users (admin only).
    
    Args:
        admin: Current admin user
        
    Returns:
        List of all users
    """
    try:
        users = await get_all_users()
        return [UserListResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            created_at=u.created_at
        ) for u in users]
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(500, "Failed to retrieve users")


@router.post("", response_model=UserListResponse, status_code=201)
async def create_new_user(request: CreateUserRequest, admin = Depends(require_admin)):
    """
    Create a new user (admin only).
    
    Args:
        request: User creation data
        admin: Current admin user
        
    Returns:
        Created user information
    """
    try:
        # Check if user already exists
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM auth.users WHERE email = $1",
                request.email.lower()
            )
            if existing:
                raise HTTPException(400, "User with this email already exists")

        # Create user
        user = await create_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role
        )
        
        if not user:
            raise HTTPException(500, "Failed to create user")

        return UserListResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            created_at=user.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create user error: {e}")
        raise HTTPException(500, "Failed to create user")


@router.delete("/{user_id}", status_code=204)
async def delete_user_by_id(user_id: int, admin = Depends(require_admin)):
    """
    Delete a user by ID (admin only).
    
    Args:
        user_id: ID of user to delete
        admin: Current admin user
        
    Returns:
        No content on success
    """
    try:
        # Prevent self-deletion
        if user_id == admin.id:
            raise HTTPException(400, "Cannot delete your own account")

        success = await delete_user(user_id)
        if not success:
            raise HTTPException(404, "User not found")

        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        raise HTTPException(500, "Failed to delete user")


@router.put("/{user_id}", response_model=UserListResponse)
async def update_user_by_id(user_id: int, request: UpdateUserRequest, admin = Depends(require_admin)):
    """
    Update a user by ID (admin only).
    
    Args:
        user_id: ID of user to update
        request: User update data
        admin: Current admin user
        
    Returns:
        Updated user information
    """
    try:
        # Check if email is being changed and if it's already taken
        if request.email:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT id FROM auth.users WHERE email = $1 AND id != $2",
                    request.email.lower(), user_id
                )
                if existing:
                    raise HTTPException(400, "User with this email already exists")

        # Update user
        user = await update_user(
            user_id=user_id,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role
        )
        
        if not user:
            raise HTTPException(404, "User not found")

        return UserListResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            created_at=user.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(500, "Failed to update user")
