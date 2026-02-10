"""
Task Generator Service
======================

Auto-generates tasks from document templates and ISO requirements.
"""

import logging
from typing import Dict, Any
from uuid import UUID

from ..config import settings

logger = logging.getLogger(__name__)


async def generate_tasks_for_document(
    conn,
    document_id: UUID,
    customer_id: int,
    plan_id: UUID,
    template: Dict[str, Any]
) -> int:
    """
    Generate tasks from document fillable sections.

    Returns:
        int: Number of tasks created
    """
    fillable_sections = template.get('fillable_sections') or []
    tasks_created = 0

    for section in fillable_sections:
        section_id = section.get('id') or section.get('section_id')
        section_title = section.get('title')
        section_type = section.get('type')
        is_mandatory = section.get('is_mandatory', False)
        requires_evidence = section.get('requires_evidence', False)

        # Create task for mandatory sections
        if is_mandatory:
            task_title = f"Complete: {section_title}"
            task_description = section.get('placeholder') or f"Fill in the {section_type} section"
            priority = 'high'

            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                    customer_id, plan_id, document_id, task_type, task_scope,
                    section_id, title, description, status, priority,
                    requires_evidence, evidence_description, auto_generated
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, customer_id, plan_id, document_id, 'fillable_section', 'document',
                section_id, task_title, task_description, 'pending', priority,
                requires_evidence, section.get('evidence_description'), True)

            tasks_created += 1

        # Create separate evidence task if needed
        elif requires_evidence:
            task_title = f"Provide Evidence: {section_title}"
            task_description = section.get('evidence_description') or "Upload required evidence"

            await conn.execute(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                    customer_id, plan_id, document_id, task_type, task_scope,
                    section_id, title, description, status, priority,
                    requires_evidence, evidence_description, auto_generated
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, customer_id, plan_id, document_id, 'evidence_required', 'document',
                section_id, task_title, task_description, 'pending', 'medium',
                True, section.get('evidence_description'), True)

            tasks_created += 1

    return tasks_created


async def generate_customer_level_tasks(
    conn,
    customer_id: int,
    plan_id: UUID,
    iso_standard_code: str
) -> int:
    """
    Generate customer-level and ISO-specific tasks.

    Returns:
        int: Number of tasks created
    """
    tasks_created = 0

    # Common customer-level tasks for all ISOs
    common_tasks = [
        {
            'title': 'Collect Company Organization Chart',
            'description': 'Obtain current organizational structure and reporting hierarchy',
            'task_type': 'custom',
            'task_scope': 'customer',
            'priority': 'high',
            'requires_evidence': True,
            'evidence_description': 'Organization chart (PDF, image, or document)',
            'evidence_format': 'document'
        },
        {
            'title': 'Collect List of Key Personnel and Roles',
            'description': 'Document key personnel responsible for ISO implementation',
            'task_type': 'custom',
            'task_scope': 'customer',
            'priority': 'high',
            'requires_evidence': False
        }
    ]

    # ISO-specific tasks
    iso_specific_tasks = []

    if iso_standard_code.startswith('ISO 27001'):
        iso_specific_tasks.extend([
            {
                'title': 'Inventory IT Assets',
                'description': 'Create inventory of all IT assets (hardware, software, data)',
                'task_type': 'custom',
                'task_scope': 'iso_plan',
                'priority': 'high',
                'requires_evidence': True,
                'evidence_description': 'Asset inventory spreadsheet',
                'evidence_format': 'document'
            },
            {
                'title': 'Risk Assessment - Initial',
                'description': 'Conduct initial information security risk assessment',
                'task_type': 'custom',
                'task_scope': 'iso_plan',
                'priority': 'urgent',
                'requires_evidence': True,
                'evidence_description': 'Risk assessment report',
                'evidence_format': 'report'
            },
            {
                'title': 'Schedule Management Review Meeting',
                'description': f'Schedule initial management review for {iso_standard_code}',
                'task_type': 'custom',
                'task_scope': 'iso_plan',
                'priority': 'medium',
                'requires_evidence': False
            }
        ])

    elif iso_standard_code.startswith('ISO 9001'):
        iso_specific_tasks.extend([
            {
                'title': 'Map Current Processes',
                'description': 'Document existing quality management processes',
                'task_type': 'custom',
                'task_scope': 'iso_plan',
                'priority': 'high',
                'requires_evidence': False
            },
            {
                'title': 'Identify Quality Metrics',
                'description': 'Define measurable quality objectives and KPIs',
                'task_type': 'custom',
                'task_scope': 'iso_plan',
                'priority': 'high',
                'requires_evidence': False
            }
        ])

    # Create all tasks
    all_tasks = common_tasks + iso_specific_tasks

    for task_data in all_tasks:
        await conn.execute(f"""
            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_tasks (
                customer_id, plan_id, document_id, task_type, task_scope,
                title, description, status, priority,
                requires_evidence, evidence_description, evidence_format, auto_generated
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """, customer_id, plan_id, None, task_data['task_type'], task_data['task_scope'],
            task_data['title'], task_data['description'], 'pending', task_data['priority'],
            task_data.get('requires_evidence', False),
            task_data.get('evidence_description'),
            task_data.get('evidence_format'),
            True)

        tasks_created += 1

    return tasks_created
