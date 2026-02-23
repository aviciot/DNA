"""
Placeholder Service
===================
Core logic for the 3-layer sync:
  customer_profile_data  → permanent knowledge base
  customer_placeholders  → collection status per plan
  customer_tasks         → action items for pending placeholders

Called whenever templates are assigned to a customer plan.
"""

import logging
from typing import List, Dict, Any
from uuid import UUID
from .customer_document_service import snapshot_template_for_customer

logger = logging.getLogger(__name__)


async def sync_placeholders_for_plan(
    conn,
    customer_id: int,
    plan_id: UUID,
    template_rows: List[Dict[str, Any]],
    created_by: int
) -> Dict[str, int]:
    """
    Main entry point. Call this whenever templates are assigned to a plan.

    For each unique placeholder across all templates:
    - If already in customer_profile_data → mark collected, auto-fill documents
    - If new → insert into customer_placeholders (pending) + create one task

    Returns counts: {auto_filled, tasks_created, placeholders_added}
    """
    # Step 1: Extract all unique placeholders across all templates
    # key → {display_label, data_type, is_required, question_title, template_ids[]}
    placeholder_map: Dict[str, Dict] = {}

    for template in template_rows:
        template_id = str(template['id'])
        structure = template['template_structure']
        if isinstance(structure, str):
            import json
            structure = json.loads(structure)

        for section in structure.get('fillable_sections', []):
            key = section.get('id') or section.get('placeholder', '').strip('{}')
            if not key:
                continue

            if key not in placeholder_map:
                placeholder_map[key] = {
                    'display_label': section.get('title', key),
                    'data_type': section.get('type', 'text'),
                    'is_required': section.get('is_mandatory', True),
                    'template_ids': [],
                    'requires_evidence': section.get('requires_evidence', False),
                    'evidence_description': section.get('evidence_description', ''),
                    'priority': section.get('priority', 'medium'),
                }
            placeholder_map[key]['template_ids'].append(UUID(template_id))

    if not placeholder_map:
        return {'auto_filled': 0, 'tasks_created': 0, 'placeholders_added': 0}

    # Snapshot each template's docx into the customer's plan folder
    iso_code = await conn.fetchval("""
        SELECT iso.code FROM dna_app.customer_iso_plans cip
        JOIN dna_app.iso_standards iso ON cip.iso_standard_id = iso.id
        WHERE cip.id = $1
    """, plan_id)

    for template in template_rows:
        await snapshot_template_for_customer(
            conn=conn,
            customer_id=customer_id,
            plan_id=plan_id,
            template_id=template['id'],
            iso_code=iso_code or '',
            created_by=created_by,
        )

    # Step 2: Check which keys already exist in customer_profile_data
    keys = list(placeholder_map.keys())
    existing_profile = await conn.fetch("""
        SELECT field_key, id, field_value
        FROM dna_app.customer_profile_data
        WHERE customer_id = $1 AND field_key = ANY($2)
    """, customer_id, keys)

    known = {row['field_key']: row for row in existing_profile}

    auto_filled = 0
    tasks_created = 0
    placeholders_added = 0

    for key, meta in placeholder_map.items():
        template_ids = meta['template_ids']

        if key in known:
            # Already collected — upsert placeholder as collected, no task
            await conn.execute("""
                INSERT INTO dna_app.customer_placeholders
                    (customer_id, plan_id, placeholder_key, display_label,
                     data_type, is_required, status, profile_data_id,
                     template_ids, collected_at)
                VALUES ($1, $2, $3, $4, $5, $6, 'collected', $7, $8, NOW())
                ON CONFLICT (customer_id, plan_id, placeholder_key)
                DO UPDATE SET
                    template_ids = EXCLUDED.template_ids,
                    status = 'collected',
                    profile_data_id = EXCLUDED.profile_data_id,
                    collected_at = NOW()
            """, customer_id, plan_id, key, meta['display_label'],
                meta['data_type'], meta['is_required'],
                known[key]['id'], template_ids)

            auto_filled += 1

        else:
            # New — insert as pending (skip if already pending from a previous sync)
            result = await conn.fetchval("""
                INSERT INTO dna_app.customer_placeholders
                    (customer_id, plan_id, placeholder_key, display_label,
                     data_type, is_required, status, template_ids)
                VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
                ON CONFLICT (customer_id, plan_id, placeholder_key)
                DO UPDATE SET
                    template_ids = EXCLUDED.template_ids
                RETURNING (xmax = 0) AS inserted  -- true if new row, false if updated
            """, customer_id, plan_id, key, meta['display_label'],
                meta['data_type'], meta['is_required'], template_ids)

            placeholders_added += 1

            # Create task only if no existing pending/in_progress task for this placeholder
            existing_task = await conn.fetchval("""
                SELECT id FROM dna_app.customer_tasks
                WHERE customer_id = $1
                  AND plan_id = $2
                  AND placeholder_key = $3
                  AND status NOT IN ('completed', 'cancelled')
                LIMIT 1
            """, customer_id, plan_id, key)

            if not existing_task:
                await conn.execute("""
                    INSERT INTO dna_app.customer_tasks (
                        customer_id, plan_id, task_type, task_scope,
                        placeholder_key, title, description, priority,
                        requires_evidence, evidence_description,
                        auto_generated, status, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, true, 'pending', $11)
                """, customer_id, plan_id,
                    'evidence_request' if meta['requires_evidence'] else 'answer_question',
                    'question',
                    key,
                    meta['display_label'],
                    meta['evidence_description'] or meta['display_label'],
                    meta['priority'],
                    meta['requires_evidence'],
                    meta['evidence_description'],
                    created_by)

                tasks_created += 1

    logger.info(
        f"Plan {plan_id} sync: {auto_filled} auto-filled, "
        f"{tasks_created} tasks created, {placeholders_added} placeholders added"
    )

    return {
        'auto_filled': auto_filled,
        'tasks_created': tasks_created,
        'placeholders_added': placeholders_added
    }


async def apply_profile_answer(
    conn,
    customer_id: int,
    field_key: str,
    field_value: str,
    source: str = 'manual',
    file_path: str = None,
    file_mime_type: str = None,
    data_type: str = 'text',
    collected_via_channel_id: UUID = None,
    updated_by: int = None
) -> Dict[str, int]:
    """
    Save an answer to customer_profile_data, then:
    - Update all customer_placeholders for this key → collected
    - Update all customer_documents that have this placeholder → fill it
    - Complete all pending tasks for this placeholder

    Returns counts of what was updated.
    """
    # Upsert into profile_data
    profile_row = await conn.fetchrow("""
        INSERT INTO dna_app.customer_profile_data
            (customer_id, field_key, field_value, file_path, file_mime_type,
             data_type, source, collected_via_channel_id, collected_by, verified)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, false)
        ON CONFLICT (customer_id, field_key)
        DO UPDATE SET
            field_value = EXCLUDED.field_value,
            file_path = EXCLUDED.file_path,
            file_mime_type = EXCLUDED.file_mime_type,
            source = EXCLUDED.source,
            collected_via_channel_id = EXCLUDED.collected_via_channel_id,
            collected_by = EXCLUDED.collected_by,
            updated_at = NOW()
        RETURNING id
    """, customer_id, field_key, field_value, file_path, file_mime_type,
        data_type, source, collected_via_channel_id, updated_by)

    profile_id = profile_row['id']

    # Update all placeholders for this customer+key → collected
    placeholders_updated = await conn.fetchval("""
        UPDATE dna_app.customer_placeholders
        SET status = 'collected',
            profile_data_id = $3,
            collected_at = NOW()
        WHERE customer_id = $1 AND placeholder_key = $2
        RETURNING COUNT(*)
    """, customer_id, field_key, profile_id)

    # Complete all pending tasks for this placeholder
    tasks_completed = await conn.fetchval("""
        UPDATE dna_app.customer_tasks
        SET status = 'completed',
            answer = $3,
            answer_file_path = $4,
            answered_at = NOW(),
            answered_via = $5,
            completed_at = NOW()
        WHERE customer_id = $1
          AND placeholder_key = $2
          AND status IN ('pending', 'in_progress')
        RETURNING COUNT(*)
    """, customer_id, field_key, field_value, file_path, source)

    # Update customer_documents: fill the placeholder in content JSONB
    # and recalculate completion_percentage
    docs_updated = await conn.fetchval("""
        UPDATE dna_app.customer_documents
        SET
            content = jsonb_set(
                content,
                ARRAY['filled_placeholders', $2],
                to_jsonb($3::text)
            ),
            placeholder_fill_status = jsonb_set(
                COALESCE(placeholder_fill_status, '{}'),
                ARRAY[$2],
                '{"status": "filled", "source": "profile"}'::jsonb
            ),
            last_auto_filled_at = NOW(),
            updated_at = NOW()
        WHERE customer_id = $1
          AND content ? 'filled_placeholders'
        RETURNING COUNT(*)
    """, customer_id, field_key, field_value)

    logger.info(
        f"Applied answer for {field_key} (customer {customer_id}): "
        f"{placeholders_updated} placeholders, {tasks_completed} tasks, {docs_updated} docs updated"
    )

    return {
        'placeholders_updated': placeholders_updated or 0,
        'tasks_completed': tasks_completed or 0,
        'docs_updated': docs_updated or 0
    }
