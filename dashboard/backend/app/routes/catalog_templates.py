"""
DNA Backend - Template Catalog Routes (CORRECT APPROACH)
=========================================================
Routes for managing templates with fixed/fillable sections.
"""

import json
import logging
from typing import List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..database import get_db_pool
from ..auth import get_current_user, require_admin
from ..config import settings

router = APIRouter(prefix="/catalog-templates", tags=["Catalog Templates"])
logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================

class FillableSection(BaseModel):
    """A fillable section in the template."""
    id: str
    title: str
    location: str
    type: str  # table, paragraph, list, field
    semantic_tags: List[str]
    current_content: Optional[str] = None
    format: Optional[str] = None
    placeholder: Optional[str] = None
    is_mandatory: bool = False
    mandatory_confidence: float = 0.0


class FixedSection(BaseModel):
    """A fixed policy section."""
    id: str
    title: str
    content: str
    section_type: str


class TemplateMetadata(BaseModel):
    """Template metadata."""
    source_file: str
    parsed_at: str
    total_fixed_sections: int
    total_fillable_sections: int
    semantic_tags_used: List[str]


class TemplateStructure(BaseModel):
    """Complete template structure."""
    document_title: str
    fixed_sections: List[FixedSection]
    fillable_sections: List[FillableSection]
    metadata: TemplateMetadata


class TemplateListItem(BaseModel):
    """Template list item."""
    id: str
    name: str
    description: Optional[str]
    iso_standard: Optional[str]
    source_filename: Optional[str]
    status: str
    version_number: int
    restored_from_version: Optional[int]
    total_fixed_sections: int
    total_fillable_sections: int
    semantic_tags: List[str]
    iso_codes: List[str]
    customer_document_count: int
    created_at: str
    updated_at: Optional[str] = None
    approved_at: Optional[str]


class TemplateDetail(BaseModel):
    """Full template details."""
    id: str
    name: str
    description: Optional[str]
    iso_standard: Optional[str]
    template_file_id: Optional[str]
    source_filename: Optional[str]
    source_file_path: Optional[str]
    template_structure: Any
    status: str
    version: Optional[str]
    version_number: int
    restored_from_version: Optional[int]
    total_fixed_sections: int
    total_fillable_sections: int
    semantic_tags: List[str]
    iso_codes: List[str]
    iso_standard_ids: Optional[List[str]] = []
    customer_document_count: int
    created_at: str
    updated_at: str
    approved_at: Optional[str]
    created_by_email: Optional[str]
    approved_by_email: Optional[str]


class ISOStandardsUpdate(BaseModel):
    """Model for updating ISO standards."""
    iso_standard_ids: List[str]


class TemplateStructureUpdate(BaseModel):
    """Model for updating template structure."""
    template_structure: Any
    notes: Optional[str] = None


class TemplateVersion(BaseModel):
    """Model for template version history entry."""
    id: str
    version_number: int
    change_summary: Optional[str]
    notes: Optional[str]
    created_at: str
    created_by: Optional[int]
    created_by_email: Optional[str]
    restored_from_version: Optional[int]


# =============================================================================
# Routes
# =============================================================================

@router.get("", response_model=List[TemplateListItem])
async def list_templates(
    status: Optional[str] = None,
    iso_standard_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if iso_standard_id:
                query = f"""
                    SELECT DISTINCT t.id, t.name, t.description, t.iso_standard,
                        t.status, t.version_number, t.restored_from_version,
                        t.total_fixed_sections, t.total_fillable_sections,
                        t.semantic_tags, t.created_at, t.updated_at, t.approved_at,
                        ARRAY_AGG(DISTINCT iso.code) FILTER (WHERE iso.code IS NOT NULL) as iso_codes
                    FROM {settings.DATABASE_APP_SCHEMA}.templates t
                    INNER JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping tim ON t.id = tim.template_id
                    LEFT JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON tim.iso_standard_id = iso.id
                    WHERE tim.iso_standard_id = $1 AND t.status != 'archived'
                    GROUP BY t.id ORDER BY t.created_at DESC
                """
                rows = await conn.fetch(query, iso_standard_id)
            else:
                status_filter = status or 'archived'
                op = '=' if status else '!='
                rows = await conn.fetch(f"""
                    SELECT t.id, t.name, t.description, t.iso_standard, t.status, t.version_number,
                        t.restored_from_version, t.total_fixed_sections, t.total_fillable_sections,
                        t.semantic_tags, t.created_at, t.updated_at, t.approved_at,
                        ARRAY_AGG(DISTINCT iso.code) FILTER (WHERE iso.code IS NOT NULL) as iso_codes
                    FROM {settings.DATABASE_APP_SCHEMA}.templates t
                    LEFT JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping tim ON t.id = tim.template_id
                    LEFT JOIN {settings.DATABASE_APP_SCHEMA}.iso_standards iso ON tim.iso_standard_id = iso.id
                    WHERE t.status {op} $1
                    GROUP BY t.id ORDER BY t.created_at DESC
                """, status_filter)

            return [{
                "id": str(r["id"]), "name": r["name"], "description": r["description"],
                "iso_standard": r["iso_standard"], "source_filename": None,
                "status": r["status"], "version_number": r["version_number"],
                "restored_from_version": r["restored_from_version"],
                "total_fixed_sections": r["total_fixed_sections"],
                "total_fillable_sections": r["total_fillable_sections"],
                "semantic_tags": r["semantic_tags"] or [],
                "iso_codes": list(r["iso_codes"]) if r["iso_codes"] else [],
                "customer_document_count": 0,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "approved_at": r["approved_at"].isoformat() if r["approved_at"] else None,
            } for r in rows]
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: UUID,
    current_user=Depends(get_current_user)
):
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT t.*, u.email as created_by_email, u2.email as approved_by_email,
                    (SELECT ARRAY_AGG(tim.iso_standard_id::text)
                     FROM {settings.DATABASE_APP_SCHEMA}.template_iso_mapping tim
                     WHERE tim.template_id = t.id) as iso_standard_ids
                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                LEFT JOIN auth.users u ON t.created_by = u.id
                LEFT JOIN auth.users u2 ON t.approved_by = u2.id
                WHERE t.id = $1
            """, template_id)

            if not row:
                raise HTTPException(404, f"Template {template_id} not found")

            result = dict(row)
            if isinstance(result.get('template_structure'), str):
                result['template_structure'] = json.loads(result['template_structure'])

            return {
                "id": str(result["id"]), "name": result["name"],
                "description": result["description"], "iso_standard": result["iso_standard"],
                "template_file_id": str(result["template_file_id"]) if result.get("template_file_id") else None,
                "source_filename": None, "source_file_path": None,
                "template_structure": result["template_structure"],
                "status": result["status"], "version": result.get("version"),
                "version_number": result["version_number"],
                "restored_from_version": result.get("restored_from_version"),
                "total_fixed_sections": result["total_fixed_sections"],
                "total_fillable_sections": result["total_fillable_sections"],
                "semantic_tags": result["semantic_tags"] or [],
                "iso_standard_ids": list(result["iso_standard_ids"]) if result.get("iso_standard_ids") else [],
                "iso_codes": [],
                "customer_document_count": 0,
                "created_at": result["created_at"].isoformat() if result["created_at"] else None,
                "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None,
                "approved_at": result["approved_at"].isoformat() if result["approved_at"] else None,
                "created_by_email": result.get("created_by_email"),
                "approved_by_email": result.get("approved_by_email"),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get template: {str(e)}")


@router.patch("/{template_id}/status")
async def update_template_status(
    template_id: UUID,
    status: str,
    current_user=Depends(require_admin)
):
    """
    Update template status.

    Allowed statuses: draft, approved, archived
    """
    if status not in ['draft', 'approved', 'archived']:
        raise HTTPException(400, f"Invalid status: {status}")

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Update status
            result = await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                SET
                    status = $2,
                    updated_at = NOW(),
                    approved_at = CASE WHEN $2 = 'approved' THEN NOW() ELSE approved_at END,
                    approved_by = CASE WHEN $2 = 'approved' THEN $3 ELSE approved_by END
                WHERE id = $1
            """, template_id, status, current_user["id"])

            if result == "UPDATE 0":
                raise HTTPException(404, f"Template {template_id} not found")

            logger.info(f"Updated template {template_id} status to {status}")
            return {"message": f"Template status updated to {status}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update template {template_id} status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.post("/{template_id}/iso-standards/{iso_standard_id}")
async def assign_iso_standard(
    template_id: UUID,
    iso_standard_id: UUID,
    current_user=Depends(require_admin)
):
    """Assign an ISO standard to a template."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if template exists
            template_exists = await conn.fetchval(f"""
                SELECT EXISTS(SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1)
            """, template_id)

            if not template_exists:
                raise HTTPException(404, f"Template {template_id} not found")

            # Check if ISO standard exists
            iso_exists = await conn.fetchval(f"""
                SELECT EXISTS(SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1)
            """, iso_standard_id)

            if not iso_exists:
                raise HTTPException(404, f"ISO standard {iso_standard_id} not found")

            # Insert mapping (ignore if already exists)
            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_iso_mapping
                (template_id, iso_standard_id, created_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (template_id, iso_standard_id) DO NOTHING
            """, template_id, iso_standard_id, current_user["user_id"])

            logger.info(f"Assigned ISO standard {iso_standard_id} to template {template_id}")
            return {"message": "ISO standard assigned to template"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign ISO standard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to assign ISO standard: {str(e)}")


@router.delete("/{template_id}/iso-standards/{iso_standard_id}")
async def unassign_iso_standard(
    template_id: UUID,
    iso_standard_id: UUID,
    current_user=Depends(require_admin)
):
    """Remove ISO standard assignment from template."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(f"""
                DELETE FROM {settings.DATABASE_APP_SCHEMA}.template_iso_mapping
                WHERE template_id = $1 AND iso_standard_id = $2
            """, template_id, iso_standard_id)

            if result == "DELETE 0":
                raise HTTPException(404, "Assignment not found")

            logger.info(f"Removed ISO standard {iso_standard_id} from template {template_id}")
            return {"message": "ISO standard removed from template"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove ISO standard assignment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove assignment: {str(e)}")


@router.patch("/{template_id}/iso-standards")
async def update_iso_standards(
    template_id: UUID,
    update_data: ISOStandardsUpdate,
    current_user=Depends(require_admin)
):
    """Update ISO standards assigned to a template (replace all)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if template exists
            template_exists = await conn.fetchval(f"""
                SELECT EXISTS(SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1)
            """, template_id)

            if not template_exists:
                raise HTTPException(404, f"Template {template_id} not found")

            async with conn.transaction():
                # Delete all existing mappings
                await conn.execute(f"""
                    DELETE FROM {settings.DATABASE_APP_SCHEMA}.template_iso_mapping
                    WHERE template_id = $1
                """, template_id)

                # Insert new mappings
                if update_data.iso_standard_ids:
                    for iso_id_str in update_data.iso_standard_ids:
                        iso_id = UUID(iso_id_str)
                        await conn.execute(f"""
                            INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_iso_mapping
                            (template_id, iso_standard_id, created_by)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (template_id, iso_standard_id) DO NOTHING
                        """, template_id, iso_id, current_user["user_id"])

            logger.info(f"Updated ISO standards for template {template_id}: {len(update_data.iso_standard_ids)} standards")
            return {"message": f"Updated {len(update_data.iso_standard_ids)} ISO standard assignments"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ISO standards for template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update ISO standards: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    current_user=Depends(require_admin)
):
    """Delete a template (soft delete by setting status to archived)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Soft delete - set status to archived
            result = await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                SET status = 'archived', updated_at = NOW()
                WHERE id = $1 AND status != 'archived'
            """, template_id)

            if result == "UPDATE 0":
                raise HTTPException(404, "Template not found or already archived")

            logger.info(f"Deleted (archived) template {template_id}")
            return {"message": "Template deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


# =============================================================================
# Template Studio - Structure Editing & Version History
# =============================================================================

@router.patch("/{template_id}/structure")
async def update_template_structure(
    template_id: UUID,
    update_data: TemplateStructureUpdate,
    current_user=Depends(require_admin)
):
    """
    Update template structure (creates new version in history).

    This is the main endpoint for Template Studio editing.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get current template
                current = await conn.fetchrow(f"""
                    SELECT template_structure, version_number
                    FROM {settings.DATABASE_APP_SCHEMA}.templates
                    WHERE id = $1
                """, template_id)

                if not current:
                    raise HTTPException(404, f"Template {template_id} not found")

                old_structure = current["template_structure"]
                old_version = current["version_number"]
                new_version = old_version + 1

                # Parse template_structure if it's a string (from JSONB column)
                if isinstance(old_structure, str):
                    old_structure = json.loads(old_structure)

                # Convert new structure to dict
                new_structure_dict = update_data.template_structure.dict()

                # Generate change summary by comparing structures
                change_summary = _generate_change_summary(old_structure, new_structure_dict)

                # NOTE: Don't archive current version - it's already in history!
                # (It was saved there when we created it)

                # Update template with new structure (clear restored_from_version - this is a new edit, not a restore)
                await conn.execute(f"""
                    UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                    SET
                        template_structure = $1::JSONB,
                        version_number = $2,
                        total_fixed_sections = $3,
                        total_fillable_sections = $4,
                        restored_from_version = NULL,
                        last_edited_at = NOW(),
                        last_edited_by = $5,
                        updated_at = NOW()
                    WHERE id = $6
                """,
                json.dumps(new_structure_dict),
                new_version,
                len(update_data.template_structure.fixed_sections),
                len(update_data.template_structure.fillable_sections),
                current_user["user_id"],
                template_id)

                # Create version entry for new version
                await conn.execute(f"""
                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_versions
                    (template_id, version_number, template_structure, change_summary, notes, created_by)
                    VALUES ($1, $2, $3::JSONB, $4, $5, $6)
                """, template_id, new_version,
                     json.dumps(new_structure_dict),
                     change_summary, update_data.notes, current_user["user_id"])

                logger.info(f"Updated template {template_id} structure to version {new_version}")
                return {
                    "message": "Template structure updated",
                    "version": new_version,
                    "change_summary": change_summary
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update template structure: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update structure: {str(e)}")


@router.get("/{template_id}/versions", response_model=List[TemplateVersion])
async def get_template_versions(
    template_id: UUID,
    current_user=Depends(get_current_user)
):
    """Get version history for a template."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT
                    tv.id,
                    tv.version_number,
                    tv.change_summary,
                    tv.notes,
                    tv.created_at,
                    tv.created_by,
                    tv.restored_from_version,
                    u.email as created_by_email
                FROM {settings.DATABASE_APP_SCHEMA}.template_versions tv
                LEFT JOIN auth.users u ON tv.created_by = u.id
                WHERE tv.template_id = $1
                ORDER BY tv.version_number DESC
            """, template_id)

            versions = []
            for row in rows:
                versions.append({
                    "id": str(row["id"]),
                    "version_number": row["version_number"],
                    "change_summary": row["change_summary"],
                    "notes": row["notes"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "created_by": row["created_by"],
                    "created_by_email": row["created_by_email"],
                    "restored_from_version": row["restored_from_version"]
                })

            logger.info(f"Retrieved {len(versions)} versions for template {template_id}")
            return versions

    except Exception as e:
        logger.error(f"Failed to get template versions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get versions: {str(e)}")


@router.get("/{template_id}/versions/{version_number}")
async def get_template_version(
    template_id: UUID,
    version_number: int,
    current_user=Depends(get_current_user)
):
    """Get a specific version of a template."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT
                    tv.id,
                    tv.version_number,
                    tv.template_structure,
                    tv.change_summary,
                    tv.notes,
                    tv.created_at,
                    tv.created_by,
                    u.email as created_by_email,
                    t.name as template_name
                FROM {settings.DATABASE_APP_SCHEMA}.template_versions tv
                LEFT JOIN auth.users u ON tv.created_by = u.id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.templates t ON tv.template_id = t.id
                WHERE tv.template_id = $1 AND tv.version_number = $2
            """, template_id, version_number)

            if not row:
                raise HTTPException(404, f"Version {version_number} not found for template {template_id}")

            result = {
                "id": str(row["id"]),
                "version_number": row["version_number"],
                "template_name": row["template_name"],
                "template_structure": row["template_structure"],
                "change_summary": row["change_summary"],
                "notes": row["notes"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "created_by": row["created_by"],
                "created_by_email": row["created_by_email"]
            }

            logger.info(f"Retrieved version {version_number} for template {template_id}")
            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get version: {str(e)}")


@router.post("/{template_id}/versions/{version_number}/restore")
async def restore_template_version(
    template_id: UUID,
    version_number: int,
    current_user=Depends(require_admin)
):
    """Restore a previous version of a template (creates new version)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get the version to restore
                version_row = await conn.fetchrow(f"""
                    SELECT template_structure
                    FROM {settings.DATABASE_APP_SCHEMA}.template_versions
                    WHERE template_id = $1 AND version_number = $2
                """, template_id, version_number)

                if not version_row:
                    raise HTTPException(404, f"Version {version_number} not found")

                # Get current version number
                current_row = await conn.fetchrow(f"""
                    SELECT version_number, template_structure
                    FROM {settings.DATABASE_APP_SCHEMA}.templates
                    WHERE id = $1
                """, template_id)

                if not current_row:
                    raise HTTPException(404, f"Template {template_id} not found")

                old_version = current_row["version_number"]
                new_version = old_version + 1
                restored_structure = version_row["template_structure"]

                # Ensure structure is dict (parse if needed)
                if isinstance(restored_structure, str):
                    restored_structure = json.loads(restored_structure)

                # NOTE: Don't archive current version - it's already in history!
                # (It was saved there when we created it)

                # Count sections in restored structure
                fixed_count = len(restored_structure.get("fixed_sections", []))
                fillable_count = len(restored_structure.get("fillable_sections", []))

                # Restore template to old version (becomes new version)
                await conn.execute(f"""
                    UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                    SET
                        template_structure = $1::JSONB,
                        version_number = $2,
                        total_fixed_sections = $3,
                        total_fillable_sections = $4,
                        restored_from_version = $5,
                        last_edited_at = NOW(),
                        last_edited_by = $6,
                        updated_at = NOW()
                    WHERE id = $7
                """, json.dumps(restored_structure), new_version, fixed_count, fillable_count,
                     version_number, current_user["user_id"], template_id)

                # Create version entry for restored version
                await conn.execute(f"""
                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_versions
                    (template_id, version_number, template_structure, change_summary, created_by, restored_from_version)
                    VALUES ($1, $2, $3::JSONB, $4, $5, $6)
                """, template_id, new_version, json.dumps(restored_structure),
                     f"Restored from version {version_number}", current_user["user_id"], version_number)

                logger.info(f"Restored template {template_id} to version {version_number} (now v{new_version})")
                return {
                    "message": f"Restored to version {version_number}",
                    "new_version": new_version
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore template version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore version: {str(e)}")


@router.post("/{template_id}/sync-placeholders")
async def sync_template_placeholders(
    template_id: UUID,
    current_user=Depends(require_admin)
):
    """Sync fillable_sections from {{}} tokens in fixed_sections text. Fixes existing templates."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT template_structure, version_number FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1",
            template_id
        )
        if not row:
            raise HTTPException(404, "Template not found")
        structure = row["template_structure"]
        if isinstance(structure, str):
            structure = json.loads(structure)
        before = len(structure.get("fillable_sections", []))
        structure = _sync_fillable_from_text(structure)
        after = len(structure.get("fillable_sections", []))
        added = after - before
        new_version = row["version_number"] + 1
        await conn.execute(f"""
            UPDATE {settings.DATABASE_APP_SCHEMA}.templates
            SET template_structure = $1::JSONB,
                total_fillable_sections = $2,
                version_number = $3,
                updated_at = NOW()
            WHERE id = $4
        """, json.dumps(structure), after, new_version, template_id)
        if added:
            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_versions
                (template_id, version_number, template_structure, change_summary, created_by)
                VALUES ($1, $2, $3::JSONB, $4, $5)
            """, template_id, new_version, json.dumps(structure),
                f"Auto-synced {added} placeholder(s) from fixed section text",
                current_user.get("user_id"))
        return {"added": added, "total": after, "version": new_version}


@router.post("/sync-all-placeholders")
async def sync_all_templates_placeholders(current_user=Depends(require_admin)):
    """Sync all templates at once."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, template_structure, version_number FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE status != 'archived'"
        )
        results = []
        for row in rows:
            structure = row["template_structure"]
            if isinstance(structure, str):
                structure = json.loads(structure)
            before = len(structure.get("fillable_sections", []))
            structure = _sync_fillable_from_text(structure)
            after = len(structure.get("fillable_sections", []))
            added = after - before
            if added:
                new_version = row["version_number"] + 1
                await conn.execute(f"""
                    UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                    SET template_structure = $1::JSONB,
                        total_fillable_sections = $2,
                        version_number = $3,
                        updated_at = NOW()
                    WHERE id = $4
                """, json.dumps(structure), after, new_version, row["id"])
                results.append({"id": str(row["id"]), "added": added})
        return {"synced": len(results), "details": results}


@router.put("/{template_id}")
async def update_template(
    template_id: UUID,
    update_data: dict,
    current_user=Depends(require_admin)
):
    """Update template status or name."""
    status = update_data.get("status")
    if status and status not in ['draft', 'approved', 'archived']:
        raise HTTPException(400, f"Invalid status: {status}")
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                SET status = COALESCE($2, status),
                    updated_at = NOW(),
                    approved_at = CASE WHEN $2 = 'approved' THEN NOW() ELSE approved_at END,
                    approved_by = CASE WHEN $2 = 'approved' THEN $3 ELSE approved_by END
                WHERE id = $1
            """, template_id, status, current_user.get("user_id"))
            if result == "UPDATE 0":
                raise HTTPException(404, f"Template {template_id} not found")
            return {"message": "Template updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/{template_id}/sections")
async def update_template_sections(
    template_id: UUID,
    body: dict,
    current_user=Depends(require_admin)
):
    """Update the sections array (sections or fixed_sections) in a template's structure."""
    sections = body.get("sections")
    sections_key = body.get("sections_key", "sections")  # "sections" or "fixed_sections"
    if sections is None:
        raise HTTPException(400, "sections required")
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT template_structure, version_number FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1",
                template_id
            )
            if not row:
                raise HTTPException(404, "Template not found")
            structure = row["template_structure"]
            if isinstance(structure, str):
                structure = json.loads(structure)
            structure[sections_key] = sections
            new_version = row["version_number"] + 1
            structure_json = json.dumps(structure)
            total_fillable = len(set(re.findall(r'\{\{([^}]+)\}\}', structure_json)))
            await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                SET template_structure = $1::JSONB,
                    total_fixed_sections = $2,
                    total_fillable_sections = $3,
                    version_number = $4,
                    last_edited_at = NOW(),
                    last_edited_by = $5,
                    updated_at = NOW()
                WHERE id = $6
            """, structure_json, len(sections), total_fillable, new_version,
                current_user.get("user_id"), template_id)
            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_versions
                (template_id, version_number, template_structure, change_summary, created_by)
                VALUES ($1, $2, $3::JSONB, 'Edited template sections', $4)
            """, template_id, new_version, structure_json, current_user.get("user_id"))
            return {"message": "Saved", "version": new_version, "total_fillable_sections": total_fillable}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/{template_id}/fillable-sections")
async def save_fillable_sections(
    template_id: UUID,
    body: dict,
    current_user=Depends(require_admin)
):
    """Save edited fillable sections back into template_structure."""
    fillable_sections = body.get("fillable_sections")
    if fillable_sections is None:
        raise HTTPException(400, "fillable_sections required")
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT template_structure, version_number FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1",
                template_id
            )
            if not row:
                raise HTTPException(404, "Template not found")
            structure = row["template_structure"]
            if isinstance(structure, str):
                structure = json.loads(structure)
            structure["fillable_sections"] = fillable_sections
            new_version = row["version_number"] + 1
            await conn.execute(f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.templates
                SET template_structure = $1::JSONB,
                    total_fillable_sections = $2,
                    version_number = $3,
                    last_edited_at = NOW(),
                    last_edited_by = $4,
                    updated_at = NOW()
                WHERE id = $5
            """, json.dumps(structure), len(fillable_sections), new_version,
                current_user.get("user_id"), template_id)
            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.template_versions
                (template_id, version_number, template_structure, change_summary, created_by)
                VALUES ($1, $2, $3::JSONB, 'Edited fillable sections', $4)
            """, template_id, new_version, json.dumps(structure), current_user.get("user_id"))
            return {"message": "Saved", "version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


import re


def _sync_fillable_from_text(structure: dict) -> dict:
    """
    Scan the entire template_structure JSON for {{key}} tokens (works for both
    legacy fixed_sections and formal sections formats). Auto-add minimal entries
    for any key not already in fillable_sections.
    """
    existing_keys = {
        (s.get("placeholder", "").strip("{}") or s.get("id", ""))
        for s in structure.get("fillable_sections", [])
    }
    new_entries = []
    for m in re.finditer(r'\{\{([^}]+)\}\}', json.dumps(structure)):
        key = m.group(1).strip()
        if key and key not in existing_keys:
            existing_keys.add(key)
            new_entries.append({
                "id": key,
                "title": key.replace("_", " ").title(),
                "placeholder": f"{{{{{key}}}}}",
                "question": f"What is the {key.replace('_', ' ')}?",
                "type": "text",
                "is_mandatory": True,
                "requires_evidence": False,
                "semantic_tags": [],
                "auto_fillable": False,
                "automation_source": "manual",
                "trigger_event": "annual_review",
            })
    if new_entries:
        structure["fillable_sections"] = structure.get("fillable_sections", []) + new_entries
    return structure


def _generate_change_summary(old_structure: dict, new_structure: dict) -> str:
    """Generate human-readable summary of changes between versions."""
    changes = []

    # Count section changes
    old_fillable = len(old_structure.get("fillable_sections", []))
    new_fillable = len(new_structure.get("fillable_sections", []))
    old_fixed = len(old_structure.get("fixed_sections", []))
    new_fixed = len(new_structure.get("fixed_sections", []))

    if new_fillable > old_fillable:
        changes.append(f"Added {new_fillable - old_fillable} fillable section(s)")
    elif new_fillable < old_fillable:
        changes.append(f"Removed {old_fillable - new_fillable} fillable section(s)")

    if new_fixed > old_fixed:
        changes.append(f"Added {new_fixed - old_fixed} fixed section(s)")
    elif new_fixed < old_fixed:
        changes.append(f"Removed {old_fixed - new_fixed} fixed section(s)")

    # Check for mandatory field changes
    old_mandatory = sum(1 for s in old_structure.get("fillable_sections", []) if s.get("is_mandatory"))
    new_mandatory = sum(1 for s in new_structure.get("fillable_sections", []) if s.get("is_mandatory"))

    if new_mandatory > old_mandatory:
        changes.append(f"Marked {new_mandatory - old_mandatory} field(s) as mandatory")
    elif new_mandatory < old_mandatory:
        changes.append(f"Unmarked {old_mandatory - new_mandatory} mandatory field(s)")

    # Check for tag changes (simplified - just count total tags)
    old_tags = sum(len(s.get("semantic_tags", [])) for s in old_structure.get("fillable_sections", []))
    new_tags = sum(len(s.get("semantic_tags", [])) for s in new_structure.get("fillable_sections", []))

    if new_tags > old_tags:
        changes.append(f"Added {new_tags - old_tags} semantic tag(s)")
    elif new_tags < old_tags:
        changes.append(f"Removed {old_tags - new_tags} semantic tag(s)")

    if not changes:
        return "Minor edits to template structure"

    return ", ".join(changes)
