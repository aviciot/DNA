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
from fastapi.responses import HTMLResponse
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


# ---------------------------------------------------------------------------
# Preview endpoint — used by template edit, customer docs, final generation
# ---------------------------------------------------------------------------

@router.get("/preview/template/{template_id}", response_class=HTMLResponse)
async def preview_template(
    template_id: UUID,
    lang: str = "en",
    filled_data: Optional[str] = None,  # JSON string of {placeholder: value}
    current_user=Depends(get_current_user)
):
    """
    Render a template as styled HTML using the design config for the given language.
    - filled_data: optional JSON of placeholder values (for customer doc preview)
    - Placeholders without values are shown as highlighted {{tags}}
    """
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
            # fallback to English
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

    html = _render_html(tmpl["name"], structure, cfg, direction, values)
    return HTMLResponse(content=html)


def _render_html(title: str, structure: dict, cfg: dict, direction: str, values: dict) -> str:
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
        f'<h1 style="{section_style(title_st)}">{placeholder_html(title)}</h1>'
    )

    # Fixed sections
    for sec in structure.get("fixed_sections", []):
        sec_type = sec.get("section_type", "body")
        content = sec.get("content", "")
        if sec_type in ("heading", "title"):
            body_parts.append(f'<h2 style="{section_style(heading_st)}">{placeholder_html(content)}</h2>')
        elif sec_type == "subheading":
            body_parts.append(f'<h3 style="{section_style(subheading_st)}">{placeholder_html(content)}</h3>')
        else:
            body_parts.append(f'<p style="{section_style(body_st)}">{placeholder_html(content)}</p>')

    # Fillable sections
    for sec in structure.get("fillable_sections", []):
        sec_title = sec.get("title", "")
        sec_type = sec.get("type", "paragraph")
        current = sec.get("current_content", "") or sec.get("placeholder", f"{{{{{sec.get('id','field')}}}}}")

        if sec_title:
            body_parts.append(f'<h3 style="{section_style(subheading_st)}">{placeholder_html(sec_title)}</h3>')

        if sec_type == "table":
            tbl_st = st.get("table", {})
            body_parts.append(
                f'<table style="width:100%;border-collapse:collapse;{section_style(body_st)}">'
                f'<tr><td style="background:{tbl_st.get("header_bg","#1e3a5f")};'
                f'color:{tbl_st.get("header_color","#fff")};'
                f'padding:{tbl_st.get("cell_padding","8px 12px")}">'
                f'{placeholder_html(current)}</td></tr></table>'
            )
        elif sec_type == "list":
            list_st = st.get("list", {})
            items = current.split("\n") if "\n" in current else [current]
            items_html = "".join(
                f'<li style="margin-bottom:{list_st.get("spacing_after",4)}px">{placeholder_html(item)}</li>'
                for item in items if item.strip()
            )
            body_parts.append(
                f'<ul style="padding-left:{list_st.get("indent_px",24)}px;{section_style(body_st)}">'
                f'{items_html}</ul>'
            )
        else:
            body_parts.append(f'<p style="{section_style(body_st)}">{placeholder_html(current)}</p>')

    body_html = "\n".join(body_parts)

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
    background: #fff;
    direction: {direction};
  }}
  .page {{
    max-width: 210mm;
    margin: 0 auto;
    padding: {margin}cm;
    background: #fff;
    min-height: 297mm;
  }}
  @media print {{
    body {{ background: #fff; }}
    .page {{ padding: {margin}cm; box-shadow: none; }}
  }}
</style>
</head>
<body>
<div class="page">
{body_html}
</div>
</body>
</html>"""
