"""
DNA Auth Service - Authentication Routes
=========================================
Login, logout, token validation, and refresh endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response

from models.schemas import LoginRequest, TokenPair
from services.password_service import authenticate_with_password
from services.token_service import create_access_token, create_refresh_token, verify_token, revoke_token
from services.user_service import get_user_by_id, update_last_login
from config.settings import settings

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


@router.post("/login", response_model=TokenPair)
async def login(login_request: LoginRequest, request: Request):
    """
    Login with email and password to get JWT tokens.
    
    Args:
        login_request: Email and password
        
    Returns:
        TokenPair with access token, refresh token, and expiry
    """
    client_ip = request.client.host if hasattr(request, 'client') else "unknown"
    logger.info(f"Login attempt from {client_ip} for {login_request.email}")

    # Authenticate user
    user = await authenticate_with_password(login_request.email, login_request.password)
    if not user:
        logger.warning(f"Login failed for {login_request.email} from {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Create tokens
    access_token = await create_access_token(user)
    refresh_token = await create_refresh_token(user)

    # Update last login
    await update_last_login(user.id)

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds

    logger.info(f"Login successful for user {user.id} ({login_request.email})")

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout and revoke token.
    
    Args:
        credentials: Bearer token from Authorization header
        
    Returns:
        Success message
    """
    if not credentials:
        raise HTTPException(401, "Authorization header required")

    try:
        await revoke_token(credentials.credentials)
        logger.info("User logged out successfully")
        return {"message": "Logout successful"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(500, "Logout failed")


@router.get("/verify")
async def verify(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify JWT token (used by backend services).
    
    Returns 200 with user info headers:
    - X-User-Id
    - X-User-Email
    - X-User-Role
    """
    if not credentials:
        raise HTTPException(401, "Authorization header required")

    try:
        payload = await verify_token(credentials.credentials)
        user_id = int(payload.get("sub"))

        # Get fresh user data
        user = await get_user_by_id(user_id)
        if not user:
            raise HTTPException(401, "User not found or inactive")

        # Return 200 with headers
        return Response(
            status_code=200,
            headers={
                "X-User-Id": str(user.id),
                "X-User-Email": user.email,
                "X-User-Role": user.role
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify error: {e}")
        raise HTTPException(401, "Token verification failed")


@router.post("/refresh", response_model=TokenPair)
async def refresh(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Refresh access token using refresh token.
    
    Args:
        credentials: Refresh token in Authorization header
        
    Returns:
        New TokenPair
    """
    if not credentials:
        raise HTTPException(401, "Authorization header required")

    try:
        # Verify refresh token
        payload = await verify_token(credentials.credentials)

        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")

        user_id = int(payload.get("sub"))
        user = await get_user_by_id(user_id)

        if not user:
            raise HTTPException(401, "User not found or inactive")

        # Create new tokens
        access_token = await create_access_token(user)
        refresh_token = await create_refresh_token(user)

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        logger.info(f"Token refreshed for user {user_id}")

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(401, "Token refresh failed")
