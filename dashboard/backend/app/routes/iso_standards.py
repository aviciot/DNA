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
from ..config import settings

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
    approved_template_count: int = 0
    customer_count: int = 0
    unique_controls_count: int = 0
    unique_clauses_count: int = 0

    class Config:
        from_attributes = True


_SELECT = """
    SELECT
        iso.id, iso.code, iso.name, iso.description,
        iso.requirements_summary, iso.active, iso.display_order,
        iso.color, iso.ai_metadata, iso.tags, iso.language, iso.created_at, iso.updated_at
"""

# Subqueries to count unique controls/clauses from actual template data (more accurate than LLM summary)
_CONTROLS_SUBQ = """(
    SELECT COUNT(DISTINCT ctrl)
    FROM {schema}.template_iso_mapping tim2
    JOIN {schema}.templates t2 ON t2.id = tim2.template_id
    CROSS JOIN LATERAL unnest(t2.covered_controls) AS ctrl
    WHERE tim2.iso_standard_id = iso.id AND t2.status != 'archived'
) as unique_controls_count"""

_CLAUSES_SUBQ = """(
    SELECT COUNT(DISTINCT cl)
    FROM {schema}.template_iso_mapping tim3
    JOIN {schema}.templates t3 ON t3.id = tim3.template_id
    CROSS JOIN LATERAL unnest(t3.covered_clauses) AS cl
    WHERE tim3.iso_standard_id = iso.id AND t3.status != 'archived'
) as unique_clauses_count"""

_CUSTOMER_SUBQ = """(
    SELECT COUNT(DISTINCT customer_id)
    FROM {schema}.customer_iso_plans
    WHERE iso_standard_id = iso.id
) as customer_count"""


@router.get("", response_model=List[ISOStandardResponse])
async def list_iso_standards(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user)
):
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            where = "WHERE iso.active = true" if active_only else ""
            sc = settings.DATABASE_APP_SCHEMA
            query = f"""
                {_SELECT},
                COUNT(DISTINCT CASE WHEN t.status != 'archived' THEN tim.template_id END) as template_count,
                COUNT(DISTINCT CASE WHEN t.status = 'approved' THEN tim.template_id END) as approved_template_count,
                {_CUSTOMER_SUBQ.format(schema=sc)},
                {_CONTROLS_SUBQ.format(schema=sc)},
                {_CLAUSES_SUBQ.format(schema=sc)}
                FROM {sc}.iso_standards iso
                LEFT JOIN {sc}.template_iso_mapping tim ON iso.id = tim.iso_standard_id
                LEFT JOIN {sc}.templates t ON tim.template_id = t.id
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
            sc = settings.DATABASE_APP_SCHEMA
            query = f"""
                {_SELECT},
                COUNT(DISTINCT tim.template_id) as template_count,
                COUNT(DISTINCT CASE WHEN t.status = 'approved' THEN tim.template_id END) as approved_template_count,
                {_CUSTOMER_SUBQ.format(schema=sc)},
                {_CONTROLS_SUBQ.format(schema=sc)},
                {_CLAUSES_SUBQ.format(schema=sc)}
                FROM {sc}.iso_standards iso
                LEFT JOIN {sc}.template_iso_mapping tim ON iso.id = tim.iso_standard_id
                LEFT JOIN {sc}.templates t ON tim.template_id = t.id
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

        # Customer document status + task completion per template
        doc_map = {}
        task_stats: dict = {}
        if customer_id:
            docs = await conn.fetch("""
                SELECT id, template_id, plan_id, document_name, status, completion_percentage,
                       mandatory_sections_completed, mandatory_sections_total
                FROM dna_app.customer_documents
                WHERE customer_id = $1 AND template_id = ANY($2::uuid[])
            """, customer_id, [t["id"] for t in templates])
            doc_map = {str(d["template_id"]): dict(d) for d in docs}

            # Task stats keyed by plan_id (new-arch tasks have document_id=NULL)
            plan_ids = list({d["plan_id"] for d in docs if d["plan_id"]})
            if plan_ids:
                task_rows = await conn.fetch("""
                    SELECT
                        plan_id,
                        COUNT(*) FILTER (WHERE status != 'cancelled'
                                         AND (is_ignored = false OR is_ignored IS NULL)) AS tasks_total,
                        COUNT(*) FILTER (WHERE status IN ('completed', 'answered')
                                         AND (is_ignored = false OR is_ignored IS NULL)) AS tasks_done
                    FROM dna_app.customer_tasks
                    WHERE customer_id = $1 AND plan_id = ANY($2::uuid[])
                    GROUP BY plan_id
                """, customer_id, plan_ids)
                task_stats = {
                    str(r["plan_id"]): {"tasks_total": int(r["tasks_total"]), "tasks_done": int(r["tasks_done"])}
                    for r in task_rows
                }

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
        plan_id_str = str(doc["plan_id"]) if doc and doc.get("plan_id") else None
        ts = task_stats.get(plan_id_str) if plan_id_str else None
        tmpl_data = {
            "id": tmpl_id,
            "name": tmpl["name"],
            "doc_name": doc["document_name"] if doc else None,
            "total_fillable": tmpl["total_fillable_sections"],
            "doc_status": doc["status"] if doc else None,
            "completion_pct": doc["completion_percentage"] if doc else None,
            "tasks_total": ts["tasks_total"] if ts else 0,
            "tasks_done": ts["tasks_done"] if ts else 0,
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
            grp_tasks_total = sum(d.get("tasks_total", 0) for d in all_docs)
            grp_tasks_done = sum(d.get("tasks_done", 0) for d in all_docs)
        else:
            completed = in_progress = grp_pct = grp_tasks_total = grp_tasks_done = 0

        groups_out.append({
            "key": gk,
            "is_annex": grp["is_annex"],
            "total_clauses": len(clauses),
            "covered_clauses": grp_covered,
            "completed_docs": completed,
            "inprogress_docs": in_progress,
            "completion_pct": grp_pct,
            "tasks_total": grp_tasks_total,
            "tasks_done": grp_tasks_done,
            "clauses": sorted(clauses, key=lambda c: c["ref"].replace("A.", "").zfill(8)),
        })

    overall_pct = round((covered_clauses / total_clauses * 100)) if total_clauses else 0

    # Sum directly from unique plan stats — group-level sums double-count because
    # the same plan's tasks appear once per template per group.
    summary_tasks_total = sum(v["tasks_total"] for v in task_stats.values())
    summary_tasks_done = sum(v["tasks_done"] for v in task_stats.values())

    return {
        "iso": {"id": str(iso["id"]), "code": iso["code"], "name": iso["name"], "color": iso["color"]},
        "mode": "customer" if customer_id else "plan",
        "summary": {
            "total_clauses": total_clauses,
            "covered_clauses": covered_clauses,
            "gap_clauses": total_clauses - covered_clauses,
            "coverage_pct": overall_pct,
            "total_templates": len(templates),
            "tasks_total": summary_tasks_total,
            "tasks_done": summary_tasks_done,
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

            # Check for customer plans — always block unless delete_templates=true
            plan_count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE iso_standard_id = $1",
                iso_id,
            )
            if plan_count > 0 and not delete_templates:
                raise HTTPException(
                    409,
                    f"Cannot delete: {plan_count} customer plan(s) reference this ISO standard. "
                    "Check 'Also delete templates & plans' to remove them along with all associated tasks and documents.",
                )

            if delete_templates:
                # Delete templates linked to this ISO
                await conn.execute(
                    f"""DELETE FROM {settings.DATABASE_APP_SCHEMA}.templates
                        WHERE id IN (
                            SELECT template_id FROM {settings.DATABASE_APP_SCHEMA}.template_iso_mapping
                            WHERE iso_standard_id = $1
                        )""",
                    iso_id,
                )
                # Delete customer plans (cascades to tasks, documents, placeholders, channels)
                await conn.execute(
                    f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE iso_standard_id = $1",
                    iso_id,
                )
            else:
                # Just remove the association, keep templates
                await conn.execute(
                    f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.template_iso_mapping WHERE iso_standard_id = $1",
                    iso_id,
                )

            # Always clean up build tasks (just audit logs, not user data)
            await conn.execute(
                f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.ai_tasks WHERE iso_standard_id = $1",
                iso_id,
            )

            await conn.execute(
                f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1", iso_id
            )
            logger.info(f"Deleted ISO standard {iso_id} (delete_templates={delete_templates})")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ISO standard {iso_id}: {e}")
        raise HTTPException(500, f"Failed to delete ISO standard: {str(e)}")


@router.get("/{iso_id}/placeholder-dictionary")
async def get_placeholder_dictionary(
    iso_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Return the placeholder_dictionary for an ISO standard."""
    import json as _json
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT placeholder_dictionary FROM dna_app.iso_standards WHERE id = $1", iso_id
            )
            if not row:
                raise HTTPException(404, f"ISO standard {iso_id} not found")
            raw = row["placeholder_dictionary"]
            if isinstance(raw, str):
                raw = _json.loads(raw)
            return raw or []
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get placeholder dictionary for {iso_id}: {e}")
        raise HTTPException(500, str(e))


@router.patch("/{iso_id}/placeholder-dictionary")
async def update_placeholder_dictionary(
    iso_id: UUID,
    body: Dict[str, Any],
    current_user: dict = Depends(require_admin)
):
    """Replace the placeholder_dictionary for an ISO standard."""
    import json as _json
    dictionary = body.get("placeholder_dictionary")
    if dictionary is None:
        raise HTTPException(400, "placeholder_dictionary required")
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE dna_app.iso_standards SET placeholder_dictionary = $1::JSONB WHERE id = $2",
                _json.dumps(dictionary), iso_id
            )
            if result == "UPDATE 0":
                raise HTTPException(404, f"ISO standard {iso_id} not found")
            logger.info(f"Updated placeholder_dictionary for ISO standard {iso_id}: {len(dictionary)} entries")
            return {"updated": len(dictionary)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update placeholder dictionary for {iso_id}: {e}")
        raise HTTPException(500, str(e))
