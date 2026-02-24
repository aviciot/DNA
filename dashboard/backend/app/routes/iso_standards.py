"""
ISO Standards Management API
"""

import logging
from typing import List, Optional, Any, Dict
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from ..database import get_db_pool
from ..auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iso-standards", tags=["ISO Standards"])


class ISOStandardBase(BaseModel):
    code: str = Field(..., example="ISO 9001:2015")
    name: str = Field(..., example="Quality Management Systems")
    description: Optional[str] = None
    requirements_summary: Optional[str] = None
    active: bool = True
    display_order: int = 0
    color: Optional[str] = "#3b82f6"
    tags: Optional[List[str]] = []
    language: Optional[str] = "en"


class ISOStandardCreate(ISOStandardBase):
    pass


class ISOStandardUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    requirements_summary: Optional[str] = None
    active: Optional[bool] = None
    display_order: Optional[int] = None
    color: Optional[str] = None
    tags: Optional[List[str]] = None
    language: Optional[str] = None


class ISOStandardResponse(ISOStandardBase):
    id: UUID
    color: Optional[str] = "#3b82f6"
    ai_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    template_count: int = 0
    customer_count: int = 0

    class Config:
        from_attributes = True


_SELECT = """
    SELECT
        iso.id, iso.code, iso.name, iso.description,
        iso.requirements_summary, iso.active, iso.display_order,
        iso.color, iso.ai_metadata, iso.tags, iso.language, iso.created_at, iso.updated_at
"""


@router.get("", response_model=List[ISOStandardResponse])
async def list_iso_standards(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user)
):
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            where = "WHERE iso.active = true" if active_only else ""
            query = f"""
                {_SELECT},
                COUNT(DISTINCT CASE WHEN t.status != 'archived' THEN tim.template_id END) as template_count,
                0 as customer_count
                FROM dna_app.iso_standards iso
                LEFT JOIN dna_app.template_iso_mapping tim ON iso.id = tim.iso_standard_id
                LEFT JOIN dna_app.templates t ON tim.template_id = t.id
                {where}
                GROUP BY iso.id
                ORDER BY iso.display_order, iso.code
            """
            rows = await conn.fetch(query)
            result = []
            for row in rows:
                r = dict(row)
                if isinstance(r.get('ai_metadata'), str):
                    import json
                    try: r['ai_metadata'] = json.loads(r['ai_metadata'])
                    except: r['ai_metadata'] = None
                result.append(r)
            return result
    except Exception as e:
        logger.error(f"Error listing ISO standards: {e}")
        raise HTTPException(500, f"Failed to list ISO standards: {str(e)}")


@router.get("/{iso_id}", response_model=ISOStandardResponse)
async def get_iso_standard(
    iso_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = f"""
                {_SELECT},
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
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM dna_app.iso_standards WHERE code = $1", iso_data.code
            )
            if existing:
                raise HTTPException(400, f"ISO standard with code '{iso_data.code}' already exists")

            row = await conn.fetchrow("""
                INSERT INTO dna_app.iso_standards
                    (code, name, description, requirements_summary, active, display_order, color, language)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, code, name, description, requirements_summary,
                          active, display_order, color, ai_metadata, tags, language, created_at, updated_at
            """, iso_data.code, iso_data.name, iso_data.description,
                iso_data.requirements_summary, iso_data.active, iso_data.display_order,
                iso_data.color or "#3b82f6", iso_data.language or "en")

            result = dict(row)
            result['template_count'] = 0
            result['customer_count'] = 0
            logger.info(f"Created ISO standard: {iso_data.code}")
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
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM dna_app.iso_standards WHERE id = $1", iso_id
            )
            if not existing:
                raise HTTPException(404, f"ISO standard {iso_id} not found")

            updates, values, i = [], [], 1
            for field in ("code", "name", "description", "requirements_summary",
                          "active", "display_order", "color", "language"):
                val = getattr(iso_data, field)
                if val is not None:
                    updates.append(f"{field} = ${i}")
                    values.append(val)
                    i += 1

            # tags must be cast explicitly for asyncpg
            if iso_data.tags is not None:
                updates.append(f"tags = ${i}::text[]")
                values.append(iso_data.tags)
                i += 1

            if not updates:
                raise HTTPException(400, "No fields to update")

            updates.append("updated_at = NOW()")
            values.append(iso_id)

            row = await conn.fetchrow(
                f"""UPDATE dna_app.iso_standards SET {', '.join(updates)} WHERE id = ${i}
                RETURNING id, code, name, description, requirements_summary,
                          active, display_order, color, ai_metadata, tags, language, created_at, updated_at""",
                *values
            )

            result = dict(row)
            if isinstance(result.get('ai_metadata'), str):
                import json as _json
                try: result['ai_metadata'] = _json.loads(result['ai_metadata'])
                except: result['ai_metadata'] = None
            result['template_count'] = 0
            result['customer_count'] = 0
            logger.info(f"Updated ISO standard {iso_id}")
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
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM dna_app.iso_standards WHERE id = $1", iso_id
            )
            if not existing:
                raise HTTPException(404, f"ISO standard {iso_id} not found")

            template_count = await conn.fetchval(
                "SELECT COUNT(*) FROM dna_app.template_iso_mapping WHERE iso_standard_id = $1", iso_id
            )
            if template_count > 0:
                raise HTTPException(400,
                    f"Cannot delete: {template_count} template(s) are using it. Mark as inactive instead.")

            await conn.execute("DELETE FROM dna_app.iso_standards WHERE id = $1", iso_id)
            logger.info(f"Deleted ISO standard {iso_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ISO standard {iso_id}: {e}")
        raise HTTPException(500, f"Failed to delete ISO standard: {str(e)}")
