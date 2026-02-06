"""
DNA Backend - Authentication Middleware
========================================
Verify JWT tokens with auth service.
"""

import logging
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx

from .config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer()


async def verify_token(token: str) -> dict:
    """
    Verify JWT token with auth service.
    
    Returns:
        User info dict with id, email, role
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            
            if response.status_code == 200:
                # Extract user info from headers
                return {
                    "user_id": int(response.headers.get("X-User-Id", 0)),
                    "email": response.headers.get("X-User-Email", ""),
                    "role": response.headers.get("X-User-Role", "viewer")
                }
            else:
                raise HTTPException(401, "Invalid token")
                
    except httpx.RequestError as e:
        logger.error(f"Auth service connection error: {e}")
        raise HTTPException(503, "Authentication service unavailable")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(401, "Token verification failed")


async def get_current_user(credentials: HTTPAuthorizationCredentials = security) -> dict:
    """
    FastAPI dependency to get current authenticated user.
    
    Returns:
        User info dict
    """
    if not credentials:
        raise HTTPException(401, "Authorization header required")
    
    return await verify_token(credentials.credentials)


async def require_admin(user: dict = None) -> dict:
    """
    FastAPI dependency to require admin role.
    """
    if not user:
        raise HTTPException(401, "Authentication required")
    
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    
    return user
