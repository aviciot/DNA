"""
DNA Auth Service - Pydantic Models
===================================
Data validation models for API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
import re


class User(BaseModel):
    """User model."""
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class TokenPair(BaseModel):
    """JWT token pair response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """Login request."""
    email: str
    password: str
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format (lenient to allow .local domains)."""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v.lower()


class UserResponse(BaseModel):
    """User response for /me endpoint."""
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    last_login: Optional[datetime]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    timestamp: str
    database: str


class CreateUserRequest(BaseModel):
    """Create user request."""
    email: EmailStr
    password: str
    full_name: str
    role: str = "viewer"
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role."""
        if v not in ['admin', 'viewer']:
            raise ValueError('Role must be either admin or viewer')
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class UserListResponse(BaseModel):
    """User list response."""
    id: int
    email: str
    full_name: Optional[str]
    role: str
    created_at: datetime


class UpdateUserRequest(BaseModel):
    """Update user request."""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate role if provided."""
        if v is not None and v not in ['admin', 'viewer']:
            raise ValueError('Role must be either admin or viewer')
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Validate password strength if provided."""
        if v is not None and len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class Role(BaseModel):
    """Role model."""
    id: int
    name: str
    description: Optional[str]
    permissions: dict
    is_system: bool
    created_at: datetime
    updated_at: datetime


class CreateRoleRequest(BaseModel):
    """Create role request."""
    name: str
    description: Optional[str] = None
    permissions: dict = {"tabs": [], "chatwidget": False}
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate role name."""
        if len(v) < 3:
            raise ValueError('Role name must be at least 3 characters long')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Role name can only contain letters, numbers, hyphens and underscores')
        return v.lower()
    
    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v: dict) -> dict:
        """Validate permissions structure."""
        if 'tabs' not in v:
            v['tabs'] = []
        if 'chatwidget' not in v:
            v['chatwidget'] = False
        
        valid_tabs = ['dashboard', 'customers', 'documents', 'admin', 'iam']
        for tab in v['tabs']:
            if tab not in valid_tabs:
                raise ValueError(f'Invalid tab: {tab}. Must be one of: {", ".join(valid_tabs)}')
        
        return v


class UpdateRoleRequest(BaseModel):
    """Update role request."""
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[dict] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate role name if provided."""
        if v is not None:
            if len(v) < 3:
                raise ValueError('Role name must be at least 3 characters long')
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError('Role name can only contain letters, numbers, hyphens and underscores')
            return v.lower()
        return v
    
    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v: Optional[dict]) -> Optional[dict]:
        """Validate permissions structure if provided."""
        if v is not None:
            if 'tabs' not in v:
                v['tabs'] = []
            if 'chatwidget' not in v:
                v['chatwidget'] = False
            
            valid_tabs = ['dashboard', 'customers', 'documents', 'admin', 'iam']
            for tab in v['tabs']:
                if tab not in valid_tabs:
                    raise ValueError(f'Invalid tab: {tab}. Must be one of: {", ".join(valid_tabs)}')
        
        return v


class RoleListResponse(BaseModel):
    """Role list response."""
    id: int
    name: str
    description: Optional[str]
    permissions: dict
    is_system: bool
    created_at: datetime
