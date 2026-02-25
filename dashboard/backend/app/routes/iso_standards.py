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


@router.get("/{iso_id}/templates", response_model=List[Dict[str, Any]])
async def get_iso_templates(
    iso_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Return templates associated with this ISO standard."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT t.id, t.name, t.status, t.total_fillable_sections
                FROM dna_app.templates t
                JOIN dna_app.template_iso_mapping tim ON tim.template_id = t.id
                WHERE tim.iso_standard_id = $1
                ORDER BY t.name
            """, iso_id)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching templates for ISO {iso_id}: {e}")
        raise HTTPException(500, str(e))


@router.get("/{iso_id}/coverage-graph")
async def get_coverage_graph(
    iso_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Return clause/control → template coverage data for graph visualization."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        iso = await conn.fetchrow(
            "SELECT code, name, color FROM dna_app.iso_standards WHERE id = $1", iso_id
        )
        if not iso:
            raise HTTPException(404, "ISO standard not found")
        templates = await conn.fetch("""
            SELECT t.id, t.name, t.covered_clauses, t.covered_controls
            FROM dna_app.templates t
            JOIN dna_app.template_iso_mapping tim ON tim.template_id = t.id
            WHERE tim.iso_standard_id = $1 AND t.status != 'archived'
            ORDER BY t.name
        """, iso_id)

    nodes, edges = [], []
    root_id = str(iso_id)
    nodes.append({"id": root_id, "label": iso["code"], "type": "iso", "color": iso["color"] or "#3b82f6"})

    clause_seen = set()
    for tmpl in templates:
        tmpl_id = str(tmpl["id"])
        nodes.append({"id": tmpl_id, "label": tmpl["name"], "type": "template"})
        all_refs = list(tmpl["covered_clauses"] or []) + list(tmpl["covered_controls"] or [])
        # Only top-level refs (no sub-clauses like 4.1.1 if 4.1 exists)
        top_refs = [r for r in all_refs if not any(
            r != other and r.startswith(other + ".") for other in all_refs
        )]
        for ref in top_refs:
            if ref not in clause_seen:
                clause_seen.add(ref)
                is_control = ref.startswith("A.")
                nodes.append({"id": ref, "label": ref, "type": "control" if is_control else "clause"})
                edges.append({"source": root_id, "target": ref})
            edges.append({"source": ref, "target": tmpl_id})

    return {"nodes": nodes, "edges": edges, "iso": {"code": iso["code"], "name": iso["name"]}}



@router.get("/{iso_id}/coverage")
async def get_iso_coverage(
    iso_id: UUID,
    customer_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns clause/control coverage tree for an ISO standard.
    In plan mode (no customer_id): shows which clauses have templates and which are gaps.
    In customer mode (with customer_id): adds document status + completion % per template.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        iso = await conn.fetchrow(
            "SELECT id, code, name, color, ai_metadata FROM dna_app.iso_standards WHERE id = $1", iso_id
        )
        if not iso:
            raise HTTPException(404, "ISO standard not found")

        templates = await conn.fetch("""
            SELECT t.id, t.name, t.covered_clauses, t.covered_controls,
                   t.total_fillable_sections, t.status as template_status
            FROM dna_app.templates t
            JOIN dna_app.template_iso_mapping tim ON tim.template_id = t.id
            WHERE tim.iso_standard_id = $1 AND t.status != 'archived'
            ORDER BY t.name
        """, iso_id)

        # Customer document status per template
        doc_map = {}
        if customer_id:
            docs = await conn.fetch("""
                SELECT template_id, status, completion_percentage,
                       mandatory_sections_completed, mandatory_sections_total
                FROM dna_app.customer_documents
                WHERE customer_id = $1 AND template_id = ANY($2::uuid[])
            """, customer_id, [t["id"] for t in templates])
            doc_map = {str(d["template_id"]): dict(d) for d in docs}

    import json as _json
    ai_meta = iso["ai_metadata"]
    if isinstance(ai_meta, str):
        try: ai_meta = _json.loads(ai_meta)
        except: ai_meta = {}
    ai_meta = ai_meta or {}

    # Build clause groups from templates
    # Group: numeric clauses by top-level number, Annex A controls by A.X group
    clause_groups: Dict[str, Any] = {}

    for tmpl in templates:
        tmpl_id = str(tmpl["id"])
        doc = doc_map.get(tmpl_id)
        tmpl_data = {
            "id": tmpl_id,
            "name": tmpl["name"],
            "total_fillable": tmpl["total_fillable_sections"],
            "doc_status": doc["status"] if doc else None,
            "completion_pct": doc["completion_percentage"] if doc else None,
        }

        all_refs = list(tmpl["covered_clauses"] or []) + list(tmpl["covered_controls"] or [])
        # Deduplicate to top-level only (drop 4.1.1 if 4.1 present)
        top_refs = sorted(set([
            r for r in all_refs
            if not any(r != o and r.startswith(o + ".") for o in all_refs)
        ]))

        for ref in top_refs:
            # Determine group key: "4" for clause 4.x, "A.5" for A.5.x
            parts = ref.split(".")
            if ref.startswith("A.") and len(parts) >= 2:
                group_key = f"A.{parts[1]}"
            else:
                group_key = parts[0]

            if group_key not in clause_groups:
                clause_groups[group_key] = {"key": group_key, "clauses": {}, "is_annex": ref.startswith("A.")}

            if ref not in clause_groups[group_key]["clauses"]:
                clause_groups[group_key]["clauses"][ref] = {"ref": ref, "templates": []}

            clause_groups[group_key]["clauses"][ref]["templates"].append(tmpl_data)

    # Compute coverage stats per group
    groups_out = []
    total_clauses = 0
    covered_clauses = 0

    for gk, grp in sorted(clause_groups.items(), key=lambda x: (
        x[0].startswith("A."), x[0].replace("A.", "").zfill(4)
    )):
        clauses = list(grp["clauses"].values())
        total_clauses += len(clauses)
        grp_covered = sum(1 for c in clauses if c["templates"])
        covered_clauses += grp_covered

        # Customer completion per group
        if customer_id:
            all_docs = [d for c in clauses for d in c["templates"] if d["doc_status"]]
            completed = sum(1 for d in all_docs if d["doc_status"] in ("approved", "completed"))
            in_progress = sum(1 for d in all_docs if d["doc_status"] == "in_progress")
            grp_pct = round(sum(d["completion_pct"] or 0 for d in all_docs) / len(all_docs)) if all_docs else 0
        else:
            completed = in_progress = grp_pct = 0

        groups_out.append({
            "key": gk,
            "is_annex": grp["is_annex"],
            "total_clauses": len(clauses),
            "covered_clauses": grp_covered,
            "completed_docs": completed,
            "inprogress_docs": in_progress,
            "completion_pct": grp_pct,
            "clauses": sorted(clauses, key=lambda c: c["ref"].replace("A.", "").zfill(8)),
        })

    overall_pct = round((covered_clauses / total_clauses * 100)) if total_clauses else 0

    return {
        "iso": {"id": str(iso["id"]), "code": iso["code"], "name": iso["name"], "color": iso["color"]},
        "mode": "customer" if customer_id else "plan",
        "summary": {
            "total_clauses": total_clauses,
            "covered_clauses": covered_clauses,
            "gap_clauses": total_clauses - covered_clauses,
            "coverage_pct": overall_pct,
            "total_templates": len(templates),
        },
        "groups": groups_out,
    }


@router.get("/{iso_id}/export-zip")
async def export_iso_zip(
    iso_id: UUID,
    lang: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Generate a ZIP of all templates for this ISO as PDFs."""
    import io, zipfile, json as _json
    from weasyprint import HTML as WeasyprintHTML
    from ..routes.document_design import _render_html

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        iso = await conn.fetchrow("SELECT code, name FROM dna_app.iso_standards WHERE id = $1", iso_id)
        if not iso:
            raise HTTPException(404, "ISO standard not found")
        templates = await conn.fetch("""
            SELECT t.id, t.name, t.template_structure
            FROM dna_app.templates t
            JOIN dna_app.template_iso_mapping tim ON tim.template_id = t.id
            WHERE tim.iso_standard_id = $1 ORDER BY t.name
        """, iso_id)
        design = await conn.fetchrow(
            "SELECT config, direction FROM dna_app.document_design_configs WHERE language = $1 AND is_default = true LIMIT 1", lang
        ) or await conn.fetchrow(
            "SELECT config, direction FROM dna_app.document_design_configs WHERE language = 'en' AND is_default = true LIMIT 1"
        )

    cfg = design["config"] if isinstance(design["config"], dict) else _json.loads(design["config"])
    direction = design["direction"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for tmpl in templates:
            structure = tmpl["template_structure"]
            if isinstance(structure, str):
                structure = _json.loads(structure)
            html = _render_html(tmpl["name"], structure, cfg, direction, {})
            pdf = WeasyprintHTML(string=html).write_pdf()
            safe_name = tmpl["name"].replace("/", "-").replace("\\", "-").strip() or str(tmpl["id"])
            zf.writestr(f"{safe_name}.pdf", pdf)

    from urllib.parse import quote
    zip_name = iso["code"].replace(" ", "_").replace("/", "-")
    encoded = quote(f"{zip_name}.zip")
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}.zip"; filename*=UTF-8\'\'{encoded}'}
    )


@router.delete("/{iso_id}", status_code=204)
async def delete_iso_standard(
    iso_id: UUID,
    delete_templates: bool = False,
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

            if delete_templates:
                # Delete templates linked to this ISO, then mappings, then the ISO
                await conn.execute("""
                    DELETE FROM dna_app.templates
                    WHERE id IN (
                        SELECT template_id FROM dna_app.template_iso_mapping WHERE iso_standard_id = $1
                    )
                """, iso_id)
            else:
                # Just remove the association, keep templates
                await conn.execute(
                    "DELETE FROM dna_app.template_iso_mapping WHERE iso_standard_id = $1", iso_id
                )

            await conn.execute("DELETE FROM dna_app.iso_standards WHERE id = $1", iso_id)
            logger.info(f"Deleted ISO standard {iso_id} (delete_templates={delete_templates})")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ISO standard {iso_id}: {e}")
        raise HTTPException(500, f"Failed to delete ISO standard: {str(e)}")
