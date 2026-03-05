"""
Task Generator Service
======================

Auto-generates tasks and seeds customer_placeholders from template fillable_sections.
"""

import logging
import json
import re as _re
from typing import Dict, Any, List
from uuid import UUID

from ..config import settings

logger = logging.getLogger(__name__)


async def reconcile_plan(conn, customer_id: int, plan_id: UUID) -> dict:
    """
    Full plan reconciliation after any document deletion or content change.

    Scans ALL surviving document contents → builds the active {{key}} set, then:
      1. Seeds customer_placeholders for brand-new keys (lookup metadata from
         iso_standards.placeholder_dictionary; fall back to key-derived label)
      2. Creates customer_tasks for keys that have no task yet
      3. Reactivates cancelled tasks whose key is still present
      4. Cancels active tasks whose key is gone from every document

    Idempotent — safe to call multiple times.
    """
    # ── 1. Collect active keys from all surviving documents ──────────────────
    docs = await conn.fetch(
        f"SELECT content, template_id FROM {settings.DATABASE_APP_SCHEMA}.customer_documents "
        f"WHERE customer_id = $1 AND plan_id = $2",
        customer_id, plan_id
    )

    active_keys: list = []          # ordered, deduplicated
    key_to_template: dict = {}      # key → template_id string (first doc that has it)
    seen: set = set()
    for doc in docs:
        content = doc["content"]
        if not content:
            continue
        text = json.dumps(content) if isinstance(content, dict) else str(content)
        for m in _re.finditer(r'\{\{([^}]+)\}\}', text):
            key = m.group(1).strip()
            if key not in seen:
                seen.add(key)
                active_keys.append(key)
                key_to_template[key] = str(doc["template_id"]) if doc["template_id"] else None

    # ── 2. Load master placeholder dictionary for metadata fallback ──────────
    row = await conn.fetchrow(f"""
        SELECT s.placeholder_dictionary
        FROM {settings.DATABASE_APP_SCHEMA}.iso_standards s
        JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p ON p.iso_standard_id = s.id
        WHERE p.id = $1
    """, plan_id)
    raw_dict = row["placeholder_dictionary"] if row else None
    if raw_dict and isinstance(raw_dict, str):
        raw_dict = json.loads(raw_dict)
    dict_map = {e["key"]: e for e in (raw_dict or [])}

    # ── 3. Seed customer_placeholders for any brand-new keys ─────────────────
    #    ON CONFLICT DO NOTHING: never overwrite user's custom questions/labels
    seeded = 0
    for key in active_keys:
        d = dict_map.get(key) or {}
        question      = d.get("question")      or key.replace("_", " ").title()
        display_label = d.get("label")         or key.replace("_", " ").title()
        category      = d.get("category")      or "General"
        hint          = d.get("hint")
        data_type     = d.get("data_type")     or "text"
        is_required   = d.get("is_required") if d.get("is_required") is not None else True

        existing_answer = await conn.fetchrow(
            f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_profile_data "
            f"WHERE customer_id = $1 AND field_key = $2",
            customer_id, key
        )
        initial_status  = "collected" if existing_answer else "pending"
        profile_data_id = existing_answer["id"] if existing_answer else None
        tmpl_id_str     = key_to_template.get(key)

        result = await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                (customer_id, plan_id, placeholder_key, display_label, question,
                 category, hint, data_type, is_required, status,
                 profile_data_id,
                 template_ids)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    CASE WHEN $12::text IS NOT NULL
                         THEN ARRAY[$12::uuid] ELSE ARRAY[]::uuid[] END)
            ON CONFLICT (customer_id, plan_id, placeholder_key) DO NOTHING
        """, customer_id, plan_id, key, display_label, question,
            category, hint, data_type, is_required, initial_status,
            profile_data_id, tmpl_id_str)
        if result == "INSERT 0 1":
            seeded += 1

    # ── 4. Create tasks for active required keys that have no task at all ────
    tasks_created = 0
    for key in active_keys:
        ph = await conn.fetchrow(f"""
            SELECT question, display_label, hint, is_required
            FROM {settings.DATABASE_APP_SCHEMA}.customer_placeholders
            WHERE customer_id = $1 AND plan_id = $2 AND placeholder_key = $3
        """, customer_id, plan_id, key)

        if not ph or not ph["is_required"]:
            continue  # skip optional placeholders

        existing_task = await conn.fetchrow(f"""
            SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
            WHERE customer_id = $1 AND plan_id = $2
              AND placeholder_key = $3 AND auto_generated = true
        """, customer_id, plan_id, key)

        if not existing_task:
            title = ph["question"] or ph["display_label"] or key.replace("_", " ").title()
            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                    customer_id, plan_id, task_type, task_scope,
                    section_id, title, description, status, priority,
                    requires_evidence, auto_generated, placeholder_key
                )
                VALUES ($1, $2, 'fillable_section', 'iso_plan',
                        $3, $4, $5, 'pending', 'high', false, true, $3)
            """, customer_id, plan_id, key, title, ph["hint"] or "")
            tasks_created += 1

    # ── 5. Reactivate cancelled tasks whose key is still present ─────────────
    reactivated = 0
    if active_keys:
        reactivated = await conn.fetchval(f"""
            WITH upd AS (
                UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                SET status = 'pending', updated_at = NOW()
                WHERE customer_id = $1 AND plan_id = $2
                  AND auto_generated = true
                  AND placeholder_key = ANY($3::text[])
                  AND status = 'cancelled'
                RETURNING id
            ) SELECT COUNT(*) FROM upd
        """, customer_id, plan_id, active_keys) or 0

    # ── 6. Cancel tasks for keys no longer in any document ───────────────────
    #    (when active_keys=[], cancels everything — all docs were deleted)
    cancelled = await conn.fetchval(f"""
        WITH upd AS (
            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
            SET status = 'cancelled', updated_at = NOW()
            WHERE customer_id = $1 AND plan_id = $2
              AND auto_generated = true
              AND placeholder_key IS NOT NULL
              AND placeholder_key != ALL($3::text[])
              AND status NOT IN ('completed', 'cancelled')
            RETURNING id
        ) SELECT COUNT(*) FROM upd
    """, customer_id, plan_id, active_keys) or 0

    logger.info(
        f"reconcile_plan plan={plan_id} customer={customer_id}: "
        f"active_keys={len(active_keys)} seeded={seeded} tasks_created={tasks_created} "
        f"reactivated={reactivated} cancelled={cancelled}"
    )
    return {
        "active_keys": len(active_keys),
        "seeded": seeded,
        "tasks_created": tasks_created,
        "reactivated": int(reactivated),
        "cancelled": int(cancelled),
    }

def _get_structure(template: Dict[str, Any]) -> dict:
    structure = template.get('template_structure') or {}
    if isinstance(structure, str):
        structure = json.loads(structure)
    return structure


async def seed_placeholders(conn, customer_id: int, plan_id: UUID, template: Dict[str, Any]) -> int:
    """
    UPSERT customer_placeholders for a template.
    Looks up question/label/category from iso_standards.placeholder_dictionary via the plan.
    Falls back to key.replace('_', ' ').title() for standards built before this change.
    """
    structure = _get_structure(template)
    template_id = template['id']

    # Find all {{keys}} used anywhere in this template
    all_text = json.dumps(structure)
    used_keys = {m.group(1).strip() for m in _re.finditer(r'\{\{([^}]+)\}\}', all_text)}
    if not used_keys:
        return 0

    # Load placeholder_dictionary from iso_standards via the plan — one JOIN, no extra table
    row = await conn.fetchrow(f"""
        SELECT s.placeholder_dictionary
        FROM {settings.DATABASE_APP_SCHEMA}.iso_standards s
        JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p ON p.iso_standard_id = s.id
        WHERE p.id = $1
    """, plan_id)
    raw = row['placeholder_dictionary'] if row else None
    if raw and isinstance(raw, str):
        raw = json.loads(raw)
    dict_map = {entry['key']: entry for entry in (raw or [])}

    seeded = 0
    for key in used_keys:
        d = dict_map.get(key) or {}
        question = d.get('question') or key.replace('_', ' ').title()
        display_label = d.get('label') or key.replace('_', ' ').title()
        category = d.get('category') or 'General'
        hint = d.get('hint')
        data_type = d.get('data_type') or 'text'
        is_required = d.get('is_required') if d.get('is_required') is not None else True

        existing_answer = await conn.fetchrow(
            f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_profile_data "
            f"WHERE customer_id = $1 AND field_key = $2",
            customer_id, key
        )
        initial_status = 'collected' if existing_answer else 'pending'
        profile_data_id = existing_answer['id'] if existing_answer else None

        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                (customer_id, plan_id, placeholder_key, display_label, question,
                 category, hint, data_type, is_required, status,
                 profile_data_id, template_ids)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, ARRAY[$12::uuid])
            ON CONFLICT (customer_id, plan_id, placeholder_key) DO UPDATE SET
                template_ids = array_append(
                    COALESCE(customer_placeholders.template_ids, ARRAY[]::uuid[]),
                    $12::uuid
                ),
                question    = COALESCE(NULLIF(customer_placeholders.question, ''), EXCLUDED.question),
                category    = COALESCE(NULLIF(customer_placeholders.category, 'General'), EXCLUDED.category),
                profile_data_id = COALESCE(customer_placeholders.profile_data_id, EXCLUDED.profile_data_id),
                status = CASE WHEN customer_placeholders.status = 'collected' THEN 'collected' ELSE EXCLUDED.status END
        """, customer_id, plan_id, key, display_label, question,
            category, hint, data_type, is_required,
            initial_status, profile_data_id, template_id)
        seeded += 1

    return seeded


async def generate_tasks_for_document(
    conn,
    document_id: UUID,
    customer_id: int,
    plan_id: UUID,
    template: Dict[str, Any]
) -> int:
    """
    Generate tasks from document fillable_sections.
    Sets placeholder_key so the trigger chain (task→placeholder→document) works.
    """
    structure = _get_structure(template)
    fillable_sections = structure.get('fillable_sections') or []
    template_id = template.get('id')
    tasks_created = 0

    for section in fillable_sections:
        raw_placeholder = section.get('placeholder', '')
        placeholder_key = raw_placeholder.strip('{}').strip() if raw_placeholder else None
        section_id = section.get('id')
        question = section.get('question') or section.get('title', '')
        is_mandatory = section.get('is_mandatory', False)
        requires_evidence = section.get('requires_evidence', False)

        if not (is_mandatory or requires_evidence):
            continue

        task_type = 'fillable_section' if is_mandatory else 'evidence_required'
        priority = 'high' if is_mandatory else 'medium'
        title = question if question else f"Complete: {section.get('title', '')}"
        description = section.get('hint') or section.get('iso_control_title') or ''

        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                customer_id, plan_id, template_id, document_id, task_type, task_scope,
                section_id, title, description, status, priority,
                requires_evidence, evidence_description, auto_generated, placeholder_key
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT DO NOTHING
        """, customer_id, plan_id, template_id, document_id, task_type, 'document',
            section_id, title, description, 'pending', priority,
            requires_evidence, section.get('evidence_description'), True, placeholder_key)

        tasks_created += 1

    return tasks_created


async def generate_tasks_from_placeholders(
    conn,
    customer_id: int,
    plan_id: UUID,
) -> int:
    """
    Generate one task per required placeholder for a plan (new-arch approach).
    Called after all seed_placeholders() calls complete, so customer_placeholders is fully populated.
    Skips any placeholder that already has a task (idempotent).
    """
    ph_rows = await conn.fetch(f"""
        SELECT placeholder_key, question, display_label, hint
        FROM {settings.DATABASE_APP_SCHEMA}.customer_placeholders
        WHERE customer_id = $1 AND plan_id = $2 AND is_required = true
        AND NOT EXISTS (
            SELECT 1 FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks ct
            WHERE ct.customer_id = $1 AND ct.plan_id = $2
              AND ct.placeholder_key = customer_placeholders.placeholder_key
        )
        ORDER BY placeholder_key
    """, customer_id, plan_id)

    tasks_created = 0
    for ph in ph_rows:
        key = ph['placeholder_key']
        title = ph['question'] or ph['display_label'] or key.replace('_', ' ').title()
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                customer_id, plan_id, task_type, task_scope,
                section_id, title, description, status, priority,
                requires_evidence, auto_generated, placeholder_key
            )
            VALUES ($1, $2, 'fillable_section', 'iso_plan', $3, $4, $5, 'pending', 'high', false, true, $3)
        """, customer_id, plan_id, key, title, ph['hint'] or '')
        tasks_created += 1

    return tasks_created


async def generate_customer_level_tasks(
    conn,
    customer_id: int,
    plan_id: UUID,
    iso_standard_code: str
) -> int:
    """Generate standard customer-level and ISO-specific tasks."""
    tasks_created = 0

    common_tasks = [
        {
            'title': 'Collect Company Organization Chart',
            'description': 'Obtain current organizational structure and reporting hierarchy',
            'task_type': 'custom', 'task_scope': 'customer', 'priority': 'high',
            'requires_evidence': True, 'evidence_description': 'Organization chart (PDF, image, or document)',
        },
        {
            'title': 'Collect List of Key Personnel and Roles',
            'description': 'Document key personnel responsible for ISO implementation',
            'task_type': 'custom', 'task_scope': 'customer', 'priority': 'high',
            'requires_evidence': False,
        },
    ]

    iso_tasks = []
    if iso_standard_code.startswith('ISO 27001'):
        iso_tasks = [
            {'title': 'Inventory IT Assets', 'description': 'Create inventory of all IT assets',
             'task_type': 'custom', 'task_scope': 'iso_plan', 'priority': 'high',
             'requires_evidence': True, 'evidence_description': 'Asset inventory spreadsheet'},
            {'title': 'Risk Assessment - Initial', 'description': 'Conduct initial information security risk assessment',
             'task_type': 'custom', 'task_scope': 'iso_plan', 'priority': 'urgent',
             'requires_evidence': True, 'evidence_description': 'Risk assessment report'},
        ]
    elif iso_standard_code.startswith('ISO 9001'):
        iso_tasks = [
            {'title': 'Map Current Processes', 'description': 'Document existing quality management processes',
             'task_type': 'custom', 'task_scope': 'iso_plan', 'priority': 'high', 'requires_evidence': False},
        ]

    for task_data in common_tasks + iso_tasks:
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                customer_id, plan_id, document_id, task_type, task_scope,
                title, description, status, priority,
                requires_evidence, evidence_description, auto_generated
            )
            VALUES ($1, $2, NULL, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, customer_id, plan_id,
            task_data['task_type'], task_data['task_scope'],
            task_data['title'], task_data['description'], 'pending', task_data['priority'],
            task_data.get('requires_evidence', False),
            task_data.get('evidence_description'),
            True)
        tasks_created += 1

    return tasks_created
