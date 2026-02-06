"""
DNA Auth Service - Role Routes
===============================
Role management endpoints for granular access control.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from config.database import get_db_pool
from models.schemas import Role, CreateRoleRequest, UpdateRoleRequest, RoleListResponse
from routes.users import require_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[RoleListResponse])
async def list_roles(admin = Depends(require_admin)):
    """
    List all roles (admin only).
    
    Args:
        admin: Current admin user
        
    Returns:
        List of all roles
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, name, description, permissions, is_system, created_at
                FROM auth.roles
                ORDER BY is_system DESC, name ASC
            """)
            
            return [RoleListResponse(**dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"List roles error: {e}")
        raise HTTPException(500, "Failed to retrieve roles")


@router.post("", response_model=RoleListResponse, status_code=201)
async def create_role(request: CreateRoleRequest, admin = Depends(require_admin)):
    """
    Create a new role (admin only).
    
    Args:
        request: Role creation data
        admin: Current admin user
        
    Returns:
        Created role information
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if role already exists
            existing = await conn.fetchrow(
                "SELECT id FROM auth.roles WHERE name = $1",
                request.name
            )
            if existing:
                raise HTTPException(400, "Role with this name already exists")
            
            # Create role
            row = await conn.fetchrow("""
                INSERT INTO auth.roles (name, description, permissions, is_system)
                VALUES ($1, $2, $3, false)
                RETURNING id, name, description, permissions, is_system, created_at
            """, request.name, request.description, request.permissions)
            
            if not row:
                raise HTTPException(500, "Failed to create role")
            
            return RoleListResponse(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create role error: {e}")
        raise HTTPException(500, "Failed to create role")


@router.put("/{role_id}", response_model=RoleListResponse)
async def update_role(role_id: int, request: UpdateRoleRequest, admin = Depends(require_admin)):
    """
    Update a role by ID (admin only).
    
    Args:
        role_id: ID of role to update
        request: Role update data
        admin: Current admin user
        
    Returns:
        Updated role information
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if role exists and if it's a system role
            role = await conn.fetchrow(
                "SELECT is_system, name FROM auth.roles WHERE id = $1",
                role_id
            )
            if not role:
                raise HTTPException(404, "Role not found")
            if role['is_system']:
                raise HTTPException(400, "Cannot modify system roles")
            
            # Check if new name conflicts
            if request.name and request.name != role['name']:
                existing = await conn.fetchrow(
                    "SELECT id FROM auth.roles WHERE name = $1 AND id != $2",
                    request.name, role_id
                )
                if existing:
                    raise HTTPException(400, "Role with this name already exists")
            
            # Build update query
            updates = []
            params = []
            param_count = 1
            
            if request.name is not None:
                updates.append(f"name = ${param_count}")
                params.append(request.name)
                param_count += 1
            
            if request.description is not None:
                updates.append(f"description = ${param_count}")
                params.append(request.description)
                param_count += 1
            
            if request.permissions is not None:
                updates.append(f"permissions = ${param_count}")
                params.append(request.permissions)
                param_count += 1
            
            if not updates:
                # No updates, return current role
                row = await conn.fetchrow(
                    "SELECT id, name, description, permissions, is_system, created_at FROM auth.roles WHERE id = $1",
                    role_id
                )
                return RoleListResponse(**dict(row))
            
            # Add role_id as last parameter
            params.append(role_id)
            
            query = f"""
                UPDATE auth.roles
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, name, description, permissions, is_system, created_at
            """
            
            row = await conn.fetchrow(query, *params)
            
            if not row:
                raise HTTPException(404, "Role not found")
            
            return RoleListResponse(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update role error: {e}")
        raise HTTPException(500, "Failed to update role")


@router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: int, admin = Depends(require_admin)):
    """
    Delete a role by ID (admin only).
    
    Args:
        role_id: ID of role to delete
        admin: Current admin user
        
    Returns:
        No content on success
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if role exists and if it's a system role
            role = await conn.fetchrow(
                "SELECT is_system FROM auth.roles WHERE id = $1",
                role_id
            )
            if not role:
                raise HTTPException(404, "Role not found")
            if role['is_system']:
                raise HTTPException(400, "Cannot delete system roles")
            
            # Check if any users have this role
            user_count = await conn.fetchval(
                "SELECT COUNT(*) FROM auth.users WHERE role_id = $1",
                role_id
            )
            if user_count > 0:
                raise HTTPException(400, f"Cannot delete role: {user_count} user(s) are assigned to this role")
            
            # Delete role
            result = await conn.execute(
                "DELETE FROM auth.roles WHERE id = $1",
                role_id
            )
            
            if result.split()[-1] != "1":
                raise HTTPException(404, "Role not found")
            
            return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete role error: {e}")
        raise HTTPException(500, "Failed to delete role")
