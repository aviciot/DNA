"""
Task Generator Service
======================

Auto-generates tasks and seeds customer_placeholders from template fillable_sections.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from uuid import UUID

from ..config import settings

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "organization": "Company Info",   "identity":    "Company Info",
    "personnel":    "People & Roles", "leadership":  "People & Roles",
    "security":     "Security Controls", "access":   "Security Controls",
    "risk":         "Risk Management", "asset":      "Asset Management",
    "incident":     "Incident Management",
    "audit":        "Audit & Compliance",
    "supplier":     "Third Parties",  "legal":       "Legal & Regulatory",
}


def _derive_category(semantic_tags: list) -> str:
    for tag in (semantic_tags or []):
        if tag in CATEGORY_MAP:
            return CATEGORY_MAP[tag]
    return "General"


def _get_structure(template: Dict[str, Any]) -> dict:
    structure = template.get('template_structure') or {}
    if isinstance(structure, str):
        structure = json.loads(structure)
    return structure


async def seed_placeholders(conn, customer_id: int, plan_id: UUID, template: Dict[str, Any]) -> int:
    """
    UPSERT customer_placeholders from a template's fillable_sections.
    - Deduplicates by placeholder_key across templates (appends template_id to array)
    - Checks customer_profile_data — marks 'collected' immediately if answer exists
    Returns number of new placeholders inserted.
    """
    structure = _get_structure(template)
    fillable_sections = structure.get('fillable_sections') or []
    template_id = template['id']
    seeded = 0

    for section in fillable_sections:
        raw_placeholder = section.get('placeholder', '')
        placeholder_key = raw_placeholder.strip('{}').strip() if raw_placeholder else section.get('id')
        if not placeholder_key:
            continue

        question = section.get('question') or section.get('title')
        semantic_tags = section.get('semantic_tags') or []
        category = _derive_category(semantic_tags)
        hint = section.get('hint') or section.get('iso_control_title')
        example_value = section.get('example_value')
        display_label = section.get('title')

        # Check if answer already exists in profile_data
        existing_answer = await conn.fetchrow(
            f"""SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_profile_data
                WHERE customer_id = $1 AND field_key = $2""",
            customer_id, placeholder_key
        )
        initial_status = 'collected' if existing_answer else 'pending'
        profile_data_id = existing_answer['id'] if existing_answer else None

        # UPSERT — on conflict append template_id to array
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                (customer_id, plan_id, placeholder_key, display_label, question,
                 category, hint, example_value, semantic_tags, data_type,
                 is_required, status, profile_data_id, template_ids)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, ARRAY[$14::uuid])
            ON CONFLICT (customer_id, plan_id, placeholder_key) DO UPDATE SET
                template_ids = array_append(
                    COALESCE(customer_placeholders.template_ids, ARRAY[]::uuid[]),
                    $14::uuid
                ),
                -- keep existing question/category unless blank
                question      = COALESCE(NULLIF(customer_placeholders.question, ''), EXCLUDED.question),
                category      = COALESCE(NULLIF(customer_placeholders.category, 'General'), EXCLUDED.category),
                profile_data_id = COALESCE(customer_placeholders.profile_data_id, EXCLUDED.profile_data_id),
                status = CASE
                    WHEN customer_placeholders.status = 'collected' THEN 'collected'
                    ELSE EXCLUDED.status
                END
        """, customer_id, plan_id, placeholder_key, display_label, question,
            category, hint, example_value, semantic_tags,
            section.get('type', 'text'), section.get('is_required', True),
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
