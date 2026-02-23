"""
Customer Document Service
=========================
On plan assignment: snapshot the master template docx into a
customer-specific folder and create a customer_documents record.

Storage layout:
  /app/storage/customers/{customer_id}/plans/{plan_id}/{template_id}.docx
"""

import logging
import shutil
import os
from uuid import UUID
from typing import Optional

logger = logging.getLogger(__name__)

STORAGE_ROOT = "/app/storage"


def _customer_doc_path(customer_id: int, plan_id: UUID, template_id: UUID) -> str:
    folder = f"{STORAGE_ROOT}/customers/{customer_id}/plans/{plan_id}"
    os.makedirs(folder, exist_ok=True)
    return f"{folder}/{template_id}.docx"


async def snapshot_template_for_customer(
    conn,
    customer_id: int,
    plan_id: UUID,
    template_id: UUID,
    iso_code: str,
    created_by: Optional[int] = None,
) -> Optional[str]:
    """
    1. Look up the master docx path for the template.
    2. Copy it to the customer's plan folder.
    3. Upsert a customer_documents record with storage_path set.
    Returns the storage_path, or None if no source file found.
    """
    # Get template info + source file path
    row = await conn.fetchrow("""
        SELECT t.name, t.version_number, tf.file_path
        FROM dna_app.templates t
        LEFT JOIN dna_app.template_files tf ON t.template_file_id = tf.id
        WHERE t.id = $1
    """, template_id)

    if not row:
        logger.warning(f"Template {template_id} not found")
        return None

    source_path = row["file_path"]
    template_name = row["name"]
    version = row["version_number"] or 1

    # Try storage/templates UUID path as fallback
    if not source_path or not os.path.exists(source_path):
        uuid_path = f"{STORAGE_ROOT}/templates/{template_id}.docx"
        if os.path.exists(uuid_path):
            source_path = uuid_path
        else:
            logger.warning(f"No source docx found for template {template_id} (tried {source_path} and {uuid_path})")
            source_path = None

    dest_path = _customer_doc_path(customer_id, plan_id, template_id)

    if source_path:
        shutil.copy2(source_path, dest_path)
        logger.info(f"Snapshotted {source_path} → {dest_path}")
    else:
        # Still create the DB record, just without a file yet
        dest_path = None

    # Upsert customer_documents record
    await conn.execute("""
        INSERT INTO dna_app.customer_documents (
            customer_id, plan_id, template_id, template_name,
            document_name, iso_code, status, storage_path,
            template_version, completion_percentage, created_by
        ) VALUES ($1, $2, $3, $4, $5, $6, 'not_started', $7, $8, 0, $9)
        ON CONFLICT (customer_id, plan_id, template_id)
        DO UPDATE SET
            storage_path = COALESCE(EXCLUDED.storage_path, dna_app.customer_documents.storage_path),
            template_version = EXCLUDED.template_version,
            updated_at = NOW()
    """, customer_id, plan_id, template_id, template_name,
        template_name, iso_code, dest_path, version, created_by)

    return dest_path
