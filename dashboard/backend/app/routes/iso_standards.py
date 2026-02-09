"""
ISO Standards Management API

Endpoints for managing ISO standard types (ISO 9001, ISO 27001, etc.)
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from ..database import get_db_pool
from ..auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iso-standards", tags=["ISO Standards"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ISOStandardBase(BaseModel):
    """Base model for ISO standard"""
    code: str = Field(..., example="ISO 9001:2015", description="ISO code")
    name: str = Field(..., example="Quality Management Systems", description="ISO name")
    description: Optional[str] = Field(None, description="Full description of the standard")
    requirements_summary: Optional[str] = Field(None, description="Key requirements overview")
    active: bool = Field(True, description="Whether this ISO is active")
    display_order: int = Field(0, description="Sort order for UI display")


class ISOStandardCreate(ISOStandardBase):
    """Model for creating a new ISO standard"""
    pass


class ISOStandardUpdate(BaseModel):
    """Model for updating an ISO standard (all fields optional)"""
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    requirements_summary: Optional[str] = None
    active: Optional[bool] = None
    display_order: Optional[int] = None


class ISOStandardResponse(ISOStandardBase):
    """Response model with additional fields"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    # Stats (computed)
    template_count: int = Field(0, description="Number of templates for this ISO")
    customer_count: int = Field(0, description="Number of customers using this ISO")

    class Config:
        from_attributes = True


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=List[ISOStandardResponse])
async def list_iso_standards(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """
    List all ISO standards.

    Query Parameters:
        - active_only: If true, only return active standards (default: true)

    Returns:
        List of ISO standards with template and customer counts
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Build query
            query = """
                SELECT
                    iso.id,
                    iso.code,
                    iso.name,
                    iso.description,
                    iso.requirements_summary,
                    iso.active,
                    iso.display_order,
                    iso.created_at,
                    iso.updated_at,
                    -- Count only non-archived templates assigned to this ISO
                    COUNT(DISTINCT CASE
                        WHEN t.status != 'archived' THEN tim.template_id
                        ELSE NULL
                    END) as template_count,
                    -- Count customers (placeholder - implement when customer_iso table exists)
                    0 as customer_count
                FROM dna_app.iso_standards iso
                LEFT JOIN dna_app.template_iso_mapping tim ON iso.id = tim.iso_standard_id
                LEFT JOIN dna_app.catalog_templates t ON tim.template_id = t.id
            """

            if active_only:
                query += " WHERE iso.active = true"

            query += """
                GROUP BY iso.id
                ORDER BY iso.display_order, iso.code
            """

            rows = await conn.fetch(query)

            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error listing ISO standards: {e}")
        raise HTTPException(500, f"Failed to list ISO standards: {str(e)}")


@router.get("/{iso_id}", response_model=ISOStandardResponse)
async def get_iso_standard(
    iso_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific ISO standard by ID.

    Returns:
        ISO standard details with counts
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = """
                SELECT
                    iso.id,
                    iso.code,
                    iso.name,
                    iso.description,
                    iso.requirements_summary,
                    iso.active,
                    iso.display_order,
                    iso.created_at,
                    iso.updated_at,
                    COUNT(DISTINCT tim.template_id) as template_count,
                    0 as customer_count
                FROM dna_app.iso_standards iso
                LEFT JOIN dna_app.template_iso_mapping tim ON iso.id = tim.iso_standard_id
                WHERE iso.id = $1
                GROUP BY iso.id
            """

            row = await conn.fetchrow(query, iso_id)

            if not row:
                raise HTTPException(404, f"ISO standard {iso_id} not found")

            return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ISO standard {iso_id}: {e}")
        raise HTTPException(500, f"Failed to get ISO standard: {str(e)}")


@router.post("", response_model=ISOStandardResponse, status_code=201)
async def create_iso_standard(
    iso_data: ISOStandardCreate,
    current_user: dict = Depends(require_admin)
):
    """
    Create a new ISO standard.

    Requires: Admin role

    Returns:
        Created ISO standard
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if code already exists
            existing = await conn.fetchrow(
                "SELECT id FROM dna_app.iso_standards WHERE code = $1",
                iso_data.code
            )

            if existing:
                raise HTTPException(400, f"ISO standard with code '{iso_data.code}' already exists")

            # Insert new ISO
            row = await conn.fetchrow("""
                INSERT INTO dna_app.iso_standards (
                    code, name, description, requirements_summary, active, display_order
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, code, name, description, requirements_summary,
                          active, display_order, created_at, updated_at
            """, iso_data.code, iso_data.name, iso_data.description,
                iso_data.requirements_summary, iso_data.active, iso_data.display_order)

            result = dict(row)
            result['template_count'] = 0
            result['customer_count'] = 0

            logger.info(f"Created ISO standard: {iso_data.code} by user {current_user.get('user_id')}")

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating ISO standard: {e}")
        raise HTTPException(500, f"Failed to create ISO standard: {str(e)}")


@router.put("/{iso_id}", response_model=ISOStandardResponse)
async def update_iso_standard(
    iso_id: UUID,
    iso_data: ISOStandardUpdate,
    current_user: dict = Depends(require_admin)
):
    """
    Update an existing ISO standard.

    Requires: Admin role

    Returns:
        Updated ISO standard
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow(
                "SELECT id FROM dna_app.iso_standards WHERE id = $1",
                iso_id
            )

            if not existing:
                raise HTTPException(404, f"ISO standard {iso_id} not found")

            # Build dynamic update query
            updates = []
            values = []
            param_count = 1

            if iso_data.code is not None:
                updates.append(f"code = ${param_count}")
                values.append(iso_data.code)
                param_count += 1

            if iso_data.name is not None:
                updates.append(f"name = ${param_count}")
                values.append(iso_data.name)
                param_count += 1

            if iso_data.description is not None:
                updates.append(f"description = ${param_count}")
                values.append(iso_data.description)
                param_count += 1

            if iso_data.requirements_summary is not None:
                updates.append(f"requirements_summary = ${param_count}")
                values.append(iso_data.requirements_summary)
                param_count += 1

            if iso_data.active is not None:
                updates.append(f"active = ${param_count}")
                values.append(iso_data.active)
                param_count += 1

            if iso_data.display_order is not None:
                updates.append(f"display_order = ${param_count}")
                values.append(iso_data.display_order)
                param_count += 1

            if not updates:
                raise HTTPException(400, "No fields to update")

            # Add updated_at
            updates.append(f"updated_at = NOW()")

            # Add iso_id as last parameter
            values.append(iso_id)

            query = f"""
                UPDATE dna_app.iso_standards
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, code, name, description, requirements_summary,
                          active, display_order, created_at, updated_at
            """

            row = await conn.fetchrow(query, *values)

            result = dict(row)
            result['template_count'] = 0  # TODO: Calculate
            result['customer_count'] = 0

            logger.info(f"Updated ISO standard {iso_id} by user {current_user.get('user_id')}")

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ISO standard {iso_id}: {e}")
        raise HTTPException(500, f"Failed to update ISO standard: {str(e)}")


@router.delete("/{iso_id}", status_code=204)
async def delete_iso_standard(
    iso_id: UUID,
    current_user: dict = Depends(require_admin)
):
    """
    Delete an ISO standard.

    Requires: Admin role

    Note: This will fail if templates or customers are using this ISO.
          Consider marking as inactive instead.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow(
                "SELECT id FROM dna_app.iso_standards WHERE id = $1",
                iso_id
            )

            if not existing:
                raise HTTPException(404, f"ISO standard {iso_id} not found")

            # Check if in use
            template_count = await conn.fetchval(
                "SELECT COUNT(*) FROM dna_app.template_iso_mapping WHERE iso_standard_id = $1",
                iso_id
            )

            if template_count > 0:
                raise HTTPException(
                    400,
                    f"Cannot delete ISO standard: {template_count} template(s) are using it. "
                    "Consider marking it as inactive instead."
                )

            # Delete
            await conn.execute(
                "DELETE FROM dna_app.iso_standards WHERE id = $1",
                iso_id
            )

            logger.info(f"Deleted ISO standard {iso_id} by user {current_user.get('user_id')}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ISO standard {iso_id}: {e}")
        raise HTTPException(500, f"Failed to delete ISO standard: {str(e)}")
