"""
Document Generator Service
==========================

Generates customer documents from templates and creates associated tasks.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from ..database import get_db_pool
from ..config import settings
from .task_generator_service import generate_tasks_for_document, generate_customer_level_tasks

logger = logging.getLogger(__name__)


async def generate_documents_for_plan(
    plan_id: UUID,
    customer_id: int,
    iso_standard_id: UUID,
    template_selection_mode: str,
    selected_template_ids: Optional[List[UUID]] = None
) -> Dict[str, Any]:
    """
    Generate all documents and tasks for an ISO plan.

    Args:
        plan_id: ISO plan ID
        customer_id: Customer ID
        iso_standard_id: ISO standard ID
        template_selection_mode: 'all' or 'selective'
        selected_template_ids: List of template IDs (if selective)

    Returns:
        dict: {
            'documents_created': int,
            'tasks_created': int,
            'document_ids': List[UUID]
        }
    """
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        # Get customer and ISO standard info
        customer = await conn.fetchrow(
            f"SELECT id, name FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
            customer_id
        )

        iso_standard = await conn.fetchrow(
            f"SELECT id, code, name FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1",
            iso_standard_id
        )

        # Get templates to process
        if template_selection_mode == 'all':
            # Get all active templates for this ISO
            templates_query = f"""
                SELECT t.id, t.name, t.version_number, t.document_type,
                       t.document_title, t.fixed_sections, t.fillable_sections, t.metadata
                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                INNER JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping tim ON t.id = tim.template_id
                WHERE tim.iso_standard_id = $1 AND t.status = 'active'
                ORDER BY t.name
            """
            templates = await conn.fetch(templates_query, iso_standard_id)

        else:
            # Get selected templates from plan_templates
            templates_query = f"""
                SELECT t.id, t.name, t.version_number, t.document_type,
                       t.document_title, t.fixed_sections, t.fillable_sections, t.metadata
                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                INNER JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plan_templates pt ON t.id = pt.template_id
                WHERE pt.plan_id = $1 AND pt.included = true AND t.status = 'active'
                ORDER BY t.name
            """
            templates = await conn.fetch(templates_query, plan_id)

        document_ids = []
        total_tasks = 0

        # Generate document for each template
        for template in templates:
            try:
                # Create customer document
                document_id = await create_customer_document(
                    conn=conn,
                    customer_id=customer_id,
                    plan_id=plan_id,
                    template=template,
                    customer_name=customer['name'],
                    iso_code=iso_standard['code']
                )

                document_ids.append(document_id)

                # Generate tasks for this document
                tasks_created = await generate_tasks_for_document(
                    conn=conn,
                    document_id=document_id,
                    customer_id=customer_id,
                    plan_id=plan_id,
                    template=template
                )

                total_tasks += tasks_created

                logger.info(
                    f"Generated document {document_id} with {tasks_created} tasks "
                    f"for template '{template['name']}'"
                )

            except Exception as e:
                logger.error(f"Error generating document from template {template['id']}: {e}")
                # Continue with other templates

        # Generate customer-level and plan-level tasks
        customer_tasks = await generate_customer_level_tasks(
            conn=conn,
            customer_id=customer_id,
            plan_id=plan_id,
            iso_standard_code=iso_standard['code']
        )

        total_tasks += customer_tasks

        # Update plan status
        await conn.execute(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_iso_plans
               SET plan_status = 'generated', updated_at = NOW()
               WHERE id = $1""",
            plan_id
        )

        logger.info(
            f"Completed document generation for plan {plan_id}: "
            f"{len(document_ids)} documents, {total_tasks} tasks"
        )

        return {
            'documents_created': len(document_ids),
            'tasks_created': total_tasks,
            'document_ids': document_ids
        }


async def create_customer_document(
    conn,
    customer_id: int,
    plan_id: UUID,
    template: Dict[str, Any],
    customer_name: str,
    iso_code: str
) -> UUID:
    """
    Create a customer document from a template.

    This creates a snapshot of the template at the current version.
    """
    # Build document content (snapshot of template)
    content = {
        'document_title': template.get('document_title') or template['name'],
        'template_metadata': template.get('metadata') or {},
        'fixed_sections': template.get('fixed_sections') or [],
        'fillable_sections': []
    }

    # Process fillable sections
    fillable_sections = template.get('fillable_sections') or []
    for section in fillable_sections:
        # Create empty section for customer to fill
        content['fillable_sections'].append({
            'id': section.get('id') or section.get('section_id'),
            'title': section.get('title'),
            'type': section.get('type'),
            'is_mandatory': section.get('is_mandatory', False),
            'placeholder': section.get('placeholder'),
            'content': None,  # To be filled by customer
            'filled_at': None,
            'filled_by': None,
            'requires_evidence': section.get('requires_evidence', False),
            'evidence_description': section.get('evidence_description')
        })

    # Count mandatory sections
    mandatory_count = sum(1 for s in content['fillable_sections'] if s['is_mandatory'])

    # Generate document name
    document_name = f"{customer_name} - {template['name']}"

    # Insert document
    row = await conn.fetchrow(f"""
        INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_documents (
            customer_id, plan_id, template_id, template_version, template_name,
            document_name, document_type, iso_code, status, content,
            document_version, completion_percentage,
            mandatory_sections_total, mandatory_sections_completed
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING id
    """, customer_id, plan_id, template['id'], template['version_number'], template['name'],
        document_name, template.get('document_type'), iso_code, 'not_started',
        content, 1, 0, mandatory_count, 0)

    return row['id']
