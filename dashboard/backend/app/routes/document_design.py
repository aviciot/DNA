"""
Document Design Configuration API
===================================
Manages per-language design configs used for all document previews
(template edit, customer document prep, final generation).
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from ..database import get_db_pool
from ..auth import get_current_user, require_admin
from ..config import settings

router = APIRouter(prefix="/api/v1/document-design", tags=["Document Design"])
logger = logging.getLogger(__name__)


class DesignConfigResponse(BaseModel):
    id: str
    name: str
    language: str
    direction: str
    is_default: bool
    config: Dict[str, Any]


class DesignConfigUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


@router.get("", response_model=List[DesignConfigResponse])
async def list_design_configs(current_user=Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, name, language, direction, is_default, config "
            f"FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs ORDER BY language, name"
        )
    return [{"id": str(r["id"]), "name": r["name"], "language": r["language"],
             "direction": r["direction"], "is_default": r["is_default"],
             "config": r["config"] if isinstance(r["config"], dict) else json.loads(r["config"])}
            for r in rows]


# ---------------------------------------------------------------------------
# Preview endpoint — must be before /{config_id} to avoid UUID parse conflict
# ---------------------------------------------------------------------------

@router.get("/preview/template/{template_id}", response_class=HTMLResponse)
async def preview_template(
    template_id: UUID,
    lang: str = "en",
    filled_data: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        tmpl = await conn.fetchrow(
            f"SELECT name, template_structure FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1",
            template_id
        )
        if not tmpl:
            raise HTTPException(404, "Template not found")

        design = await conn.fetchrow(
            f"SELECT config, direction FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs "
            f"WHERE language = $1 AND is_default = true LIMIT 1",
            lang
        )
        if not design:
            design = await conn.fetchrow(
                f"SELECT config, direction FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs "
                f"WHERE language = 'en' AND is_default = true LIMIT 1"
            )

    structure = tmpl["template_structure"]
    if isinstance(structure, str):
        structure = json.loads(structure)

    cfg = design["config"] if isinstance(design["config"], dict) else json.loads(design["config"])
    direction = design["direction"]

    values = {}
    if filled_data:
        try:
            values = json.loads(filled_data)
        except Exception:
            pass

    return HTMLResponse(content=_render_html(tmpl["name"], structure, cfg, direction, values))


@router.get("/preview/template/{template_id}/pdf")
async def preview_template_pdf(
    template_id: UUID,
    lang: str = "en",
    current_user=Depends(get_current_user)
):
    from weasyprint import HTML as WeasyprintHTML
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        tmpl = await conn.fetchrow(
            f"SELECT name, template_structure FROM {settings.DATABASE_APP_SCHEMA}.templates WHERE id = $1",
            template_id
        )
        if not tmpl:
            raise HTTPException(404, "Template not found")
        design = await conn.fetchrow(
            f"SELECT config, direction FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs "
            f"WHERE language = $1 AND is_default = true LIMIT 1", lang
        )
        if not design:
            design = await conn.fetchrow(
                f"SELECT config, direction FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs "
                f"WHERE language = 'en' AND is_default = true LIMIT 1"
            )
    structure = tmpl["template_structure"]
    if isinstance(structure, str):
        structure = json.loads(structure)
    cfg = design["config"] if isinstance(design["config"], dict) else json.loads(design["config"])
    html = _render_html(tmpl["name"], structure, cfg, design["direction"], {})
    pdf_bytes = WeasyprintHTML(string=html).write_pdf()
    from urllib.parse import quote
    from datetime import date
    date_str = date.today().strftime("%Y-%m-%d")
    name = tmpl["name"]
    encoded_name = quote(f"{name}_{date_str}.pdf")
    ascii_fallback = name.encode('ascii', 'ignore').decode('ascii').replace(" ", "_").strip("_") or f"template_{template_id}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ascii_fallback}_{date_str}.pdf"; filename*=UTF-8\'\'{encoded_name}'}
    )


@router.get("/{config_id}", response_model=DesignConfigResponse)
async def get_design_config(config_id: UUID, current_user=Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT id, name, language, direction, is_default, config "
            f"FROM {settings.DATABASE_APP_SCHEMA}.document_design_configs WHERE id = $1",
            config_id
        )
    if not row:
        raise HTTPException(404, "Design config not found")
    return {"id": str(row["id"]), "name": row["name"], "language": row["language"],
            "direction": row["direction"], "is_default": row["is_default"],
            "config": row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])}


@router.put("/{config_id}", response_model=DesignConfigResponse)
async def update_design_config(
    config_id: UUID,
    body: DesignConfigUpdate,
    current_user=Depends(require_admin)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        updates, values, i = [], [], 1
        if body.name is not None:
            updates.append(f"name = ${i}"); values.append(body.name); i += 1
        if body.config is not None:
            updates.append(f"config = ${i}::jsonb"); values.append(json.dumps(body.config)); i += 1
        if not updates:
            raise HTTPException(400, "Nothing to update")
        updates.append("updated_at = NOW()")
        values.append(config_id)
        row = await conn.fetchrow(
            f"UPDATE {settings.DATABASE_APP_SCHEMA}.document_design_configs "
            f"SET {', '.join(updates)} WHERE id = ${i} "
            f"RETURNING id, name, language, direction, is_default, config",
            *values
        )
    if not row:
        raise HTTPException(404, "Design config not found")
    logger.info(f"Design config {config_id} updated by {current_user.get('user_id')}")
    return {"id": str(row["id"]), "name": row["name"], "language": row["language"],
            "direction": row["direction"], "is_default": row["is_default"],
            "config": row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])}


def _render_html(title: str, structure: dict, cfg: dict, direction: str, values: dict) -> str:
    fmt = structure.get("template_format", "legacy" if "fixed_sections" in structure else "formal")
    if fmt == "formal":
        return _render_formal_html(title, structure, cfg, direction, values)
    return _render_legacy_html(title, structure, cfg, direction, values)


def _render_legacy_html(title: str, structure: dict, cfg: dict, direction: str, values: dict) -> str:
    doc = cfg.get("document", {})
    colors = cfg.get("colors", {})
    st = cfg.get("section_types", {})

    font = doc.get("font_family", "Arial, sans-serif")
    base_size = doc.get("font_size_base", 11)
    margin = doc.get("margin_cm", 2.5)
    line_height = doc.get("line_height", 1.6)
    ph = st.get("placeholder", {})
    title_st = st.get("title", {})
    heading_st = st.get("heading", {})
    subheading_st = st.get("subheading", {})
    body_st = st.get("body", {})

    def placeholder_html(text: str) -> str:
        """Replace {{key}} with filled value or highlighted span."""
        import re
        def replace(m):
            key = m.group(1).strip()
            val = values.get(key) or values.get(f"{{{{{key}}}}}")
            if val:
                return f'<span style="color:{colors.get("text","#111827")}">{val}</span>'
            return (f'<span style="background:{ph.get("bg","#fef3c7")};'
                    f'border:{ph.get("border","1px dashed #f59e0b")};'
                    f'color:{ph.get("color","#92400e")};'
                    f'border-radius:{ph.get("border_radius","3px")};'
                    f'padding:{ph.get("padding","1px 4px")};'
                    f'font-style:italic">{{{{{key}}}}}</span>')
        return re.sub(r'\{\{([^}]+)\}\}', replace, text)

    def section_style(s: dict, align_override: str = None) -> str:
        align = align_override or s.get("align", "left")
        parts = [
            f"font-size:{s.get('font_size', base_size)}pt",
            f"font-weight:{'bold' if s.get('bold') else 'normal'}",
            f"color:{s.get('color', colors.get('text','#111827'))}",
            f"text-align:{align}",
            f"margin-top:{s.get('spacing_before',0)}px",
            f"margin-bottom:{s.get('spacing_after',10)}px",
            f"line-height:{line_height}",
        ]
        if s.get("border_bottom"):
            parts.append(f"border-bottom:{s['border_bottom']};padding-bottom:4px")
        return ";".join(parts)

    body_parts = []

    # Title
    body_parts.append(
        f'<div class="section-block"><h1 style="{section_style(title_st)}">{placeholder_html(title)}</h1></div>'
    )

    # Fixed sections
    SECTION_TYPE_MAP = {
        "policy_statement": "body", "guidance": "body", "procedure": "body",
        "heading": "heading", "title": "heading", "subheading": "subheading",
    }
    for sec in structure.get("fixed_sections", []):
        raw_type = sec.get("section_type", "body")
        sec_type = SECTION_TYPE_MAP.get(raw_type, "body")
        content = sec.get("content", "")
        title = sec.get("title", "")
        if title:
            body_parts.append(f'<div class="section-block"><h2 style="{section_style(heading_st)}">{placeholder_html(title)}</h2></div>')
        if sec_type == "heading":
            body_parts.append(f'<div class="section-block"><h2 style="{section_style(heading_st)}">{placeholder_html(content)}</h2></div>')
        elif sec_type == "subheading":
            body_parts.append(f'<div class="section-block"><h3 style="{section_style(subheading_st)}">{placeholder_html(content)}</h3></div>')
        else:
            body_parts.append(f'<div class="section-block"><p style="{section_style(body_st)}">{placeholder_html(content)}</p></div>')

    # Fillable sections
    for sec in structure.get("fillable_sections", []):
        sec_title = sec.get("title", "")
        sec_type = sec.get("type", "paragraph")
        if sec_type == "text":
            sec_type = "paragraph"
        current = sec.get("current_content", "") or sec.get("placeholder", f"{{{{{sec.get('id','field')}}}}}")

        if sec_title:
            body_parts.append(f'<div class="section-block"><h3 style="{section_style(subheading_st)}">{placeholder_html(sec_title)}</h3></div>')

        if sec_type == "table":
            tbl_st = st.get("table", {})
            body_parts.append(
                f'<div class="section-block"><table style="width:100%;border-collapse:collapse;{section_style(body_st)}">'
                f'<tr><td style="background:{tbl_st.get("header_bg","#1e3a5f")};'
                f'color:{tbl_st.get("header_color","#fff")};'
                f'padding:{tbl_st.get("cell_padding","8px 12px")}">'
                f'{placeholder_html(current)}</td></tr></table></div>'
            )
        elif sec_type == "list":
            list_st = st.get("list", {})
            items = current.split("\n") if "\n" in current else [current]
            items_html = "".join(
                f'<li style="margin-bottom:{list_st.get("spacing_after",4)}px">{placeholder_html(item)}</li>'
                for item in items if item.strip()
            )
            body_parts.append(
                f'<div class="section-block"><ul style="padding-left:{list_st.get("indent_px",24)}px;{section_style(body_st)}">'
                f'{items_html}</ul></div>'
            )
        else:
            body_parts.append(f'<div class="section-block"><p style="{section_style(body_st)}">{placeholder_html(current)}</p></div>')

    body_html = "\n".join(body_parts)

    header_align = "right" if direction == "rtl" else "left"
    footer_align = "right" if direction == "rtl" else "left"
    accent = colors.get('accent', '#1e3a5f')

    return f"""<!DOCTYPE html>
<html lang="{direction}" dir="{direction}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Hebrew:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: {font};
    font-size: {base_size}pt;
    color: {colors.get('text','#111827')};
    background: #f3f4f6;
    direction: {direction};
  }}
  .page {{
    max-width: 210mm;
    margin: 0 auto;
    padding: {margin}cm;
    padding-top: calc({margin}cm + 48px);
    padding-bottom: calc({margin}cm + 40px);
    background: #fff;
    min-height: 297mm;
    position: relative;
    box-shadow: 0 2px 16px rgba(0,0,0,0.10);
  }}
  .doc-header {{
    position: fixed;
    top: 0; left: 0; right: 0;
    background: {accent};
    color: #fff;
    padding: 10px {margin}cm;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 9pt;
    z-index: 100;
    direction: {direction};
  }}
  .doc-header .doc-title {{ font-weight: bold; font-size: 10pt; }}
  .doc-header .iso-badge {{
    background: rgba(255,255,255,0.15);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 8pt;
    letter-spacing: 0.5px;
  }}
  .doc-footer {{
    position: fixed;
    bottom: 0; left: 0; right: 0;
    border-top: 1px solid #e5e7eb;
    background: #fff;
    padding: 6px {margin}cm;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 8pt;
    color: #6b7280;
    direction: {direction};
  }}
  .section-block {{ page-break-inside: avoid; }}
  h1, h2, h3 {{ page-break-after: avoid; }}
  @page {{
    size: A4;
    margin: {margin}cm;
  }}
  @media print {{
    body {{ background: #fff; }}
    .page {{ box-shadow: none; padding: {margin}cm; }}
    .doc-header, .doc-footer {{ position: fixed; }}
  }}
</style>
</head>
<body>
<div class="doc-header">
  <span class="doc-title">{title}</span>
  <span class="iso-badge">ISO 27001</span>
</div>
<div class="page">
{body_html}
</div>
<div class="doc-footer">
  <span>{title}</span>
  <span>ISO 27001 &mdash; ISMS Documentation</span>
</div>
</body>
</html>"""


def _render_formal_html(title: str, structure: dict, cfg: dict, direction: str, values: dict) -> str:
    import re
    doc = cfg.get("document", {})
    colors = cfg.get("colors", {})
    font = doc.get("font_family", "Arial, sans-serif")
    base_size = doc.get("font_size_base", 11)
    margin = doc.get("margin_cm", 2.5)
    line_height = doc.get("line_height", 1.6)
    accent = colors.get("accent", "#1e3a5f")
    ph_cfg = cfg.get("section_types", {}).get("placeholder", {})

    def ph(text: str) -> str:
        def replace(m):
            key = m.group(1).strip()
            val = values.get(key) or values.get(f"{{{{{key}}}}}")
            if val:
                return f'<span style="color:{colors.get("text","#111827")}">{val}</span>'
            return (f'<span style="background:{ph_cfg.get("bg","#fef3c7")};'
                    f'border:{ph_cfg.get("border","1px dashed #f59e0b")};'
                    f'color:{ph_cfg.get("color","#92400e")};border-radius:3px;'
                    f'padding:1px 4px;font-style:italic">{{{{{key}}}}}</span>')
        return re.sub(r'\{\{([^}]+)\}\}', replace, text) if text else ""

    def tbl(headers: list, rows: list) -> str:
        th = "".join(f'<th style="background:{accent};color:#fff;padding:7px 10px;text-align:left;font-size:9pt">{h}</th>' for h in headers)
        body = ""
        for i, row in enumerate(rows):
            bg = "#f8fafc" if i % 2 == 0 else "#fff"
            tds = "".join(f'<td style="padding:7px 10px;border-bottom:1px solid #e5e7eb;font-size:9pt">{ph(str(c))}</td>' for c in row)
            body += f'<tr style="background:{bg}">{tds}</tr>'
        return f'<table style="width:100%;border-collapse:collapse;margin-bottom:16px"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'

    parts = []

    # Document title
    parts.append(f'<h1 style="font-size:18pt;font-weight:bold;color:{accent};border-bottom:2px solid {accent};padding-bottom:8px;margin-bottom:20px">ISMS – {ph(title)}</h1>')

    # Document Control table
    dc = structure.get("document_control", {})
    if dc:
        parts.append(f'<div class="section-block"><h2 style="font-size:13pt;font-weight:bold;color:{accent};margin:16px 0 8px">Document Control</h2>')
        dc_rows = dc.get("rows", [{"date": "{{doc_date}}", "version": "{{doc_version}}", "changed_by": "{{changed_by}}", "description": "{{change_description}}"}])
        parts.append(tbl(["Date", "Version", "Changed by", "Description"],
                         [[r.get("date",""), r.get("version",""), r.get("changed_by",""), r.get("description","")] for r in dc_rows]))
        parts.append('</div>')

    # Document Approval table
    da = structure.get("document_approval", {})
    if da:
        parts.append(f'<div class="section-block"><h2 style="font-size:13pt;font-weight:bold;color:{accent};margin:16px 0 8px">Document Approval</h2>')
        da_rows = da.get("rows", [{"date": "{{approval_date}}", "version": "{{doc_version}}", "approved_by": "{{approved_by}}"}])
        parts.append(tbl(["Date", "Version", "Approved by"],
                         [[r.get("date",""), r.get("version",""), r.get("approved_by","")] for r in da_rows]))
        parts.append('</div>')

    # Numbered sections
    body_style = f"font-size:{base_size}pt;line-height:{line_height};color:{colors.get('text','#111827')};margin-bottom:10px"
    h2_style = f"font-size:13pt;font-weight:bold;color:{accent};margin:20px 0 8px;border-bottom:1px solid #e5e7eb;padding-bottom:4px"
    h3_style = f"font-size:11pt;font-weight:bold;color:#374151;margin:14px 0 6px"

    for sec in structure.get("sections", []):
        num = sec.get("number", "")
        sec_title = sec.get("title", "")
        content = sec.get("content", "")
        parts.append(f'<div class="section-block"><h2 style="{h2_style}">{num}. {ph(sec_title)}</h2>')

        if content:
            parts.append(f'<p style="{body_style}">{ph(content)}</p>')

        # References section — render iso_clauses + annex_controls as lists
        if sec.get("iso_clauses") or sec.get("annex_controls"):
            if sec.get("iso_clauses"):
                items = "".join(f'<li style="margin-bottom:3px">{c}</li>' for c in sec["iso_clauses"])
                parts.append(f'<p style="font-size:9pt;font-weight:bold;color:#374151;margin:8px 0 4px">ISO/IEC 27001:2022</p><ul style="padding-left:20px;{body_style}">{items}</ul>')
            if sec.get("annex_controls"):
                items = "".join(f'<li style="margin-bottom:3px">{c}</li>' for c in sec["annex_controls"])
                parts.append(f'<p style="font-size:9pt;font-weight:bold;color:#374151;margin:8px 0 4px">Relevant Annex A controls</p><ul style="padding-left:20px;{body_style}">{items}</ul>')

        # Subsections
        for sub in sec.get("subsections", []):
            sub_num = sub.get("number", "")
            sub_title = sub.get("title", "")
            sub_content = sub.get("content", "")
            parts.append(f'<h3 style="{h3_style}">{sub_num} {ph(sub_title)}</h3>')
            if sub_content:
                parts.append(f'<p style="{body_style}">{ph(sub_content)}</p>')

        parts.append('</div>')

    # Appendix
    appendix = structure.get("appendix", {})
    if appendix:
        parts.append(f'<div class="section-block"><h2 style="{h2_style}">Appendix</h2>')

        annex_map = appendix.get("annex_mapping", [])
        if annex_map:
            parts.append(f'<h3 style="{h3_style}">A. Annex A Mapping</h3>')
            parts.append(tbl(["Section", "Annex A Control", "Title"],
                             [[r.get("section",""), r.get("control",""), r.get("title","")] for r in annex_map]))

        related_docs = appendix.get("related_documents", [])
        if related_docs:
            parts.append(f'<h3 style="{h3_style}">B. Related Documents</h3>')
            items = "".join(f'<li style="margin-bottom:3px">{ph(d)}</li>' for d in related_docs)
            parts.append(f'<ul style="padding-left:20px;{body_style}">{items}</ul>')

        related_risks = appendix.get("related_risks", [])
        if related_risks:
            parts.append(f'<h3 style="{h3_style}">C. Related Risks</h3>')
            items = "".join(f'<li style="margin-bottom:3px">{ph(r)}</li>' for r in related_risks)
            parts.append(f'<ul style="padding-left:20px;{body_style}">{items}</ul>')

        parts.append('</div>')

    body_html = "\n".join(parts)

    return f"""<!DOCTYPE html>
<html lang="{direction}" dir="{direction}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Hebrew:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: {font}; font-size: {base_size}pt; color: {colors.get('text','#111827')}; background: #f3f4f6; direction: {direction}; }}
  .page {{ max-width: 210mm; margin: 0 auto; padding: {margin}cm; padding-top: calc({margin}cm + 48px); padding-bottom: calc({margin}cm + 40px); background: #fff; min-height: 297mm; box-shadow: 0 2px 16px rgba(0,0,0,0.10); }}
  .doc-header {{ position: fixed; top: 0; left: 0; right: 0; background: {accent}; color: #fff; padding: 10px {margin}cm; display: flex; justify-content: space-between; align-items: center; font-size: 9pt; z-index: 100; }}
  .doc-header .doc-title {{ font-weight: bold; font-size: 10pt; }}
  .doc-header .iso-badge {{ background: rgba(255,255,255,0.15); border-radius: 4px; padding: 2px 8px; font-size: 8pt; }}
  .doc-footer {{ position: fixed; bottom: 0; left: 0; right: 0; border-top: 1px solid #e5e7eb; background: #fff; padding: 6px {margin}cm; display: flex; justify-content: space-between; font-size: 8pt; color: #6b7280; }}
  .section-block {{ page-break-inside: avoid; }}
  h1, h2, h3 {{ page-break-after: avoid; }}
  @page {{ size: A4; margin: {margin}cm; }}
  @media print {{ body {{ background: #fff; }} .page {{ box-shadow: none; padding: {margin}cm; }} }}
</style>
</head>
<body>
<div class="doc-header">
  <span class="doc-title">ISMS – {title}</span>
  <span class="iso-badge">ISO 27001</span>
</div>
<div class="page">
{body_html}
</div>
<div class="doc-footer">
  <span>{title}</span>
  <span>ISO 27001 &mdash; ISMS Documentation</span>
</div>
</body>
</html>"""
