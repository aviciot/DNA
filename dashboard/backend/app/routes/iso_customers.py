"""
ISO Customer Management API
============================

Enhanced customer management with portal credentials, storage, and ISO assignment.
"""

import json as _json
import logging
import re as _re
import secrets
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime, date

from ..database import get_db_pool
from ..auth import get_current_user, require_admin, require_operator
from ..config import settings
from ..services.storage_service import storage_service
from ..utils.credentials import generate_portal_credentials, generate_password, hash_password
from ..services.document_generator_service import generate_documents_for_plan
from ..services.task_generator_service import reconcile_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iso-customers", tags=["ISO Customers"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ISOAssignment(BaseModel):
    """ISO assignment during customer creation"""
    iso_standard_id: UUID
    template_selection_mode: str = Field("all", description="'all' or 'selective'")
    selected_template_ids: Optional[List[UUID]] = None
    target_completion_date: Optional[date] = None


class ISOCustomerCreate(BaseModel):
    """Create customer with portal and storage"""
    name: str = Field(..., description="Company name")
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    email: str = Field(..., description="Primary email")
    contact_email: Optional[str] = Field(None, description="Contact email for communication")
    document_email: Optional[str] = Field(None, description="Email for documents")
    compliance_email: Optional[str] = Field(None, description="Email for evidence/document automation")
    contract_email: Optional[str] = Field(None, description="Email for contracts/legal")

    # Portal credentials
    portal_enabled: bool = Field(False, description="Enable portal access")
    portal_username: Optional[str] = Field(None, description="Auto-generated if not provided")
    portal_password: Optional[str] = Field(None, description="Auto-generated if not provided")

    # Storage
    storage_type: str = Field("local", description="Storage type: local, google_drive, s3")

    # Optional ISO assignments
    iso_assignments: Optional[List[ISOAssignment]] = Field(None, description="ISO standards to assign")


class ISOCustomerUpdate(BaseModel):
    """Update customer"""
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    contact_email: Optional[str] = None
    document_email: Optional[str] = None
    compliance_email: Optional[str] = None
    contract_email: Optional[str] = None
    portal_enabled: Optional[bool] = None


class ISOCustomerResponse(BaseModel):
    """Customer response with all fields"""
    id: int
    name: str
    contact_person: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    email: str
    contact_email: Optional[str]
    document_email: Optional[str]
    status: str

    # Portal
    portal_username: Optional[str]
    portal_enabled: bool
    last_portal_login: Optional[datetime]

    # Storage
    storage_type: str
    storage_path: Optional[str]

    # Metadata
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    # Stats (if included)
    iso_plans_count: Optional[int] = 0
    documents_count: Optional[int] = 0

    class Config:
        from_attributes = True


class PortalCredentials(BaseModel):
    """Portal credentials response"""
    username: str
    password: str  # Only returned once on creation
    customer_id: int
    message: str = "Save these credentials - password cannot be retrieved later"


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("", response_model=List[ISOCustomerResponse])
async def list_iso_customers(
    current_user: dict = Depends(get_current_user)
):
    """
    List all ISO customers with basic stats.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT
                    c.id, c.name, c.contact_person, c.phone, c.address, c.email,
                    c.contact_email, c.document_email, c.status,
                    c.portal_username, c.portal_enabled, c.last_portal_login,
                    c.storage_type, c.storage_path,
                    c.created_by, c.created_at, c.updated_at,
                    COUNT(DISTINCT p.id) as iso_plans_count,
                    COUNT(DISTINCT d.id) as documents_count
                FROM {settings.DATABASE_APP_SCHEMA}.customers c
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p ON c.id = p.customer_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents d ON c.id = d.customer_id
                GROUP BY c.id
                ORDER BY c.name ASC
            """

            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error listing ISO customers: {e}")
        raise HTTPException(500, f"Failed to list customers: {str(e)}")


@router.get("/{customer_id}", response_model=ISOCustomerResponse)
async def get_iso_customer(
    customer_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get ISO customer by ID with stats.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT
                    c.id, c.name, c.contact_person, c.phone, c.address, c.email,
                    c.contact_email, c.document_email, c.status,
                    c.portal_username, c.portal_enabled, c.last_portal_login,
                    c.storage_type, c.storage_path,
                    c.created_by, c.created_at, c.updated_at,
                    COUNT(DISTINCT p.id) as iso_plans_count,
                    COUNT(DISTINCT d.id) as documents_count
                FROM {settings.DATABASE_APP_SCHEMA}.customers c
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_iso_plans p ON c.id = p.customer_id
                LEFT JOIN {settings.DATABASE_APP_SCHEMA}.customer_documents d ON c.id = d.customer_id
                WHERE c.id = $1
                GROUP BY c.id
            """

            row = await conn.fetchrow(query, customer_id)

            if not row:
                raise HTTPException(404, f"Customer {customer_id} not found")

            return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ISO customer {customer_id}: {e}")
        raise HTTPException(500, f"Failed to get customer: {str(e)}")


@router.post("", response_model=dict, status_code=201)
async def create_iso_customer(
    customer_data: ISOCustomerCreate,
    current_user: dict = Depends(require_operator)
):
    """
    Create ISO customer with portal credentials and storage.

    Returns:
        Customer data + portal credentials (password only returned once)
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if email exists
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE email = $1",
                customer_data.email
            )
            if existing:
                raise HTTPException(400, f"Customer with email '{customer_data.email}' already exists")

            # Generate portal credentials if portal is enabled
            portal_username = customer_data.portal_username
            portal_password = None  # Plain password (only returned once)
            portal_password_hash = None

            if customer_data.portal_enabled:
                if not portal_username or not customer_data.portal_password:
                    # Auto-generate credentials
                    portal_username, portal_password, portal_password_hash = generate_portal_credentials(
                        customer_data.name
                    )
                else:
                    # Use provided credentials
                    portal_username = customer_data.portal_username
                    portal_password = customer_data.portal_password
                    portal_password_hash = hash_password(portal_password)

            # Set contact and document emails (default to primary email)
            contact_email = customer_data.contact_email or customer_data.email
            document_email = customer_data.document_email or customer_data.email

            # Create customer record
            customer_row = await conn.fetchrow(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customers (
                    name, contact_person, phone, address, website, description, email,
                    contact_email, document_email, compliance_email, contract_email, status,
                    portal_username, portal_password_hash, portal_enabled,
                    storage_type,
                    created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING id, name, contact_person, phone, address, email,
                          contact_email, document_email, status,
                          portal_username, portal_enabled, last_portal_login,
                          storage_type, storage_path,
                          created_by, created_at, updated_at
            """, customer_data.name, customer_data.contact_person, customer_data.phone,
                customer_data.address, customer_data.website, customer_data.description,
                customer_data.email, contact_email, document_email,
                customer_data.compliance_email, customer_data.contract_email,
                'active', portal_username, portal_password_hash, customer_data.portal_enabled,
                customer_data.storage_type, current_user.get('user_id'))

            customer = dict(customer_row)
            customer_id = customer['id']

            # Create portal access token (customer-level, long-lived)
            portal_access_token = secrets.token_hex(32)
            await conn.execute(
                f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_portal_access
                    (customer_id, token, expires_at)
                    VALUES ($1, $2, NOW() + INTERVAL '1 year')
                    ON CONFLICT (customer_id) DO NOTHING""",
                customer_id, portal_access_token,
            )

            # Initialize storage
            storage_path = await storage_service.initialize_customer_storage(
                customer_id=customer_id,
                customer_name=customer_data.name,
                storage_type=customer_data.storage_type
            )

            # Update customer with storage path
            await conn.execute(
                f"UPDATE {settings.DATABASE_APP_SCHEMA}.customers SET storage_path = $1 WHERE id = $2",
                storage_path, customer_id
            )
            customer['storage_path'] = storage_path

            logger.info(f"Created ISO customer: {customer_data.name} (ID: {customer_id}) by user {current_user.get('user_id')}")

            # Process ISO assignments
            iso_plans_created = []
            if customer_data.iso_assignments:
                for assignment in customer_data.iso_assignments:
                    try:
                        iso_standard = await conn.fetchrow(
                            f"SELECT id, code, name FROM {settings.DATABASE_APP_SCHEMA}.iso_standards WHERE id = $1",
                            assignment.iso_standard_id
                        )
                        if not iso_standard:
                            logger.warning(f"ISO standard {assignment.iso_standard_id} not found, skipping")
                            continue

                        plan_name = f"{iso_standard['code']} Certification {datetime.now().year}"
                        plan_row = await conn.fetchrow(f"""
                            INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_iso_plans (
                                customer_id, iso_standard_id, plan_name, plan_status,
                                template_selection_mode, target_completion_date,
                                started_at, created_by
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            RETURNING id, plan_name, plan_status
                        """, customer_id, assignment.iso_standard_id, plan_name, 'active',
                            assignment.template_selection_mode, assignment.target_completion_date,
                            datetime.now(), current_user.get('user_id'))

                        plan_id = plan_row['id']

                        # Link templates to the plan
                        if assignment.template_selection_mode == 'all':
                            # Insert all templates mapped to this ISO standard
                            await conn.execute(f"""
                                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_iso_plan_templates
                                    (plan_id, template_id, included)
                                SELECT $1, t.id, true
                                FROM {settings.DATABASE_APP_SCHEMA}.templates t
                                JOIN {settings.DATABASE_APP_SCHEMA}.template_iso_mapping m ON m.template_id = t.id
                                WHERE m.iso_standard_id = $2 AND t.status = 'approved'
                                ON CONFLICT (plan_id, template_id) DO NOTHING
                            """, plan_id, assignment.iso_standard_id)
                        elif assignment.template_selection_mode == 'selective' and assignment.selected_template_ids:
                            for tmpl_id in assignment.selected_template_ids:
                                await conn.execute(f"""
                                    INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_iso_plan_templates
                                        (plan_id, template_id, included)
                                    VALUES ($1, $2, true)
                                    ON CONFLICT (plan_id, template_id) DO NOTHING
                                """, plan_id, tmpl_id)

                        iso_plans_created.append({
                            "plan_id": str(plan_id),
                            "iso_code": iso_standard['code'],
                            "iso_name": iso_standard['name'],
                            "plan_status": plan_row['plan_status'],
                        })
                        logger.info(f"Created ISO plan {plan_id} ({iso_standard['code']}) for customer {customer_id}")

                        # Seed documents, placeholders, and tasks
                        await generate_documents_for_plan(
                            plan_id=plan_id,
                            customer_id=customer_id,
                            iso_standard_id=assignment.iso_standard_id,
                            template_selection_mode=assignment.template_selection_mode,
                            selected_template_ids=assignment.selected_template_ids
                        )
                    except Exception as plan_err:
                        logger.error(f"Failed to create ISO plan for {assignment.iso_standard_id}: {plan_err}")

            # Build response
            response = {
                "customer": customer,
                "portal_credentials": None,
                "portal_access_token": portal_access_token,
                "iso_plans_created": iso_plans_created,
            }

            if customer_data.portal_enabled and portal_password:
                response["portal_credentials"] = {
                    "username": portal_username,
                    "password": portal_password,
                    "message": "Save these credentials - password cannot be retrieved later"
                }

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating ISO customer: {e}")
        raise HTTPException(500, f"Failed to create customer: {str(e)}")


@router.put("/{customer_id}", response_model=ISOCustomerResponse)
async def update_iso_customer(
    customer_id: int,
    customer_data: ISOCustomerUpdate,
    current_user: dict = Depends(require_operator)
):
    """
    Update ISO customer.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
                customer_id
            )
            if not existing:
                raise HTTPException(404, f"Customer {customer_id} not found")

            # Build dynamic update
            updates = []
            values = []
            param_count = 1

            for field in ["name", "contact_person", "phone", "address", "website",
                         "description", "email", "contact_email", "document_email",
                         "compliance_email", "contract_email", "portal_enabled"]:
                value = getattr(customer_data, field, None)
                if value is not None:
                    updates.append(f"{field} = ${param_count}")
                    values.append(value)
                    param_count += 1

            if not updates:
                raise HTTPException(400, "No fields to update")

            updates.append("updated_at = NOW()")
            values.append(customer_id)

            query = f"""
                UPDATE {settings.DATABASE_APP_SCHEMA}.customers
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, name, contact_person, phone, address, email,
                          contact_email, document_email, status,
                          portal_username, portal_enabled, last_portal_login,
                          storage_type, storage_path,
                          created_by, created_at, updated_at
            """

            row = await conn.fetchrow(query, *values)
            result = dict(row)
            result['iso_plans_count'] = 0
            result['documents_count'] = 0

            logger.info(f"Updated ISO customer {customer_id} by user {current_user.get('user_id')}")

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ISO customer {customer_id}: {e}")
        raise HTTPException(500, f"Failed to update customer: {str(e)}")


@router.delete("/{customer_id}", status_code=204)
async def delete_iso_customer(
    customer_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    Delete ISO customer.

    Note: Will fail if customer has ISO plans or documents.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
                customer_id
            )
            if not existing:
                raise HTTPException(404, f"Customer {customer_id} not found")

            # Check if customer has ISO plans
            plans_count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {settings.DATABASE_APP_SCHEMA}.customer_iso_plans WHERE customer_id = $1",
                customer_id
            )
            if plans_count > 0:
                raise HTTPException(
                    400,
                    f"Cannot delete customer: {plans_count} ISO plan(s) exist. Delete plans first."
                )

            # Delete customer
            await conn.execute(
                f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
                customer_id
            )

            logger.info(f"Deleted ISO customer {customer_id} by user {current_user.get('user_id')}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ISO customer {customer_id}: {e}")
        raise HTTPException(500, f"Failed to delete customer: {str(e)}")


@router.get("/{customer_id}/documents/{doc_id}/content")
async def get_document_content(
    customer_id: int,
    doc_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get full customer document content structure."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            doc = await conn.fetchrow(
                f"SELECT content FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE id = $1 AND customer_id = $2",
                doc_id, customer_id
            )
            if not doc:
                raise HTTPException(404, "Document not found")
            content = doc["content"]
            if isinstance(content, str):
                content = _json.loads(content)
            return content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document content: {e}")
        raise HTTPException(500, str(e))


@router.get("/{customer_id}/documents/{doc_id}/placeholder-dictionary")
async def get_document_placeholder_dictionary(
    customer_id: int,
    doc_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Return customer_placeholders for this document's plan as a PlaceholderEntry list."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            doc = await conn.fetchrow(
                f"SELECT plan_id FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE id = $1 AND customer_id = $2",
                doc_id, customer_id
            )
            if not doc:
                raise HTTPException(404, "Document not found")
            rows = await conn.fetch(f"""
                SELECT placeholder_key AS key, question, display_label AS label,
                       category, hint, data_type, is_required
                FROM {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                WHERE customer_id = $1 AND plan_id = $2
                ORDER BY placeholder_key
            """, customer_id, doc["plan_id"])
        return [dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching placeholder dictionary: {e}")
        raise HTTPException(500, str(e))


@router.patch("/{customer_id}/documents/{doc_id}/content")
async def update_document_content(
    customer_id: int,
    doc_id: UUID,
    body: dict,
    current_user: dict = Depends(require_operator)
):
    """
    Update customer document fillable sections and sync placeholders/tasks.
    body: { fillable_sections: [...], fixed_sections: [...] }
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            doc = await conn.fetchrow(
                f"SELECT id, customer_id, plan_id, content FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE id = $1 AND customer_id = $2",
                doc_id, customer_id
            )
            if not doc:
                raise HTTPException(404, "Document not found")

            content = doc["content"]
            if isinstance(content, str):
                content = _json.loads(content)

            # Apply structure updates (support both legacy and new-arch formats)
            fillable = body.get("fillable_sections")
            fixed = body.get("fixed_sections")
            sections = body.get("sections")
            sections_key = body.get("sections_key", "sections")

            if fillable is not None:
                content["fillable_sections"] = fillable
            if fixed is not None:
                content["fixed_sections"] = fixed
            if sections is not None:
                content[sections_key] = sections

            await conn.execute(
                f"UPDATE {settings.DATABASE_APP_SCHEMA}.customer_documents SET content = $1::jsonb, updated_at = NOW() WHERE id = $2",
                _json.dumps(content), doc_id
            )

            # Sync legacy fillable section changes to placeholders and tasks
            if fillable is not None:
                for sec in fillable:
                    ph_key = (sec.get("placeholder") or "").strip("{}")
                    if not ph_key:
                        continue
                    new_title = sec.get("title") or ""
                    new_question = sec.get("question") or ""
                    await conn.execute(f"""
                        UPDATE {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                        SET display_label = $1, question = $2, updated_at = NOW()
                        WHERE customer_id = $3 AND plan_id = $4 AND placeholder_key = $5
                    """, new_title, new_question, customer_id, doc["plan_id"], ph_key)
                    if new_title:
                        await conn.execute(f"""
                            UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                            SET title = $1, updated_at = NOW()
                            WHERE document_id = $2 AND placeholder_key = $3
                        """, new_title, doc_id, ph_key)

            # Sync new-arch placeholder_dictionary updates to customer_placeholders
            placeholder_dictionary = body.get("placeholder_dictionary")
            if placeholder_dictionary:
                for entry in placeholder_dictionary:
                    key = entry.get("key", "")
                    if not key:
                        continue
                    await conn.execute(f"""
                        UPDATE {settings.DATABASE_APP_SCHEMA}.customer_placeholders
                        SET question = $1, display_label = $2, updated_at = NOW()
                        WHERE customer_id = $3 AND plan_id = $4 AND placeholder_key = $5
                    """, entry.get("question") or "", entry.get("label") or "",
                        customer_id, doc["plan_id"], key)
                    # Also update task title to match new question
                    await conn.execute(f"""
                        UPDATE {settings.DATABASE_APP_SCHEMA}.customer_tasks
                        SET title = $1, updated_at = NOW()
                        WHERE customer_id = $2 AND plan_id = $3 AND placeholder_key = $4
                    """, entry.get("question") or entry.get("label") or key,
                        customer_id, doc["plan_id"], key)

            # Full reconciliation: seed new keys, reactivate returned, cancel removed
            sync = await reconcile_plan(conn, customer_id, doc["plan_id"])
            return {"ok": True, **sync}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document content: {e}")
        raise HTTPException(500, str(e))


@router.get("/{customer_id}/documents/{doc_id}/task-impact")
async def get_document_task_impact(
    customer_id: int,
    doc_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Preview which tasks would be cancelled if this document were deleted.

    Logic mirrors reconcile_plan: a task is impacted only if its placeholder_key
    does NOT appear in any OTHER surviving document in the same plan.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            doc = await conn.fetchrow(
                f"SELECT id, plan_id, document_name, content FROM {settings.DATABASE_APP_SCHEMA}.customer_documents "
                f"WHERE id = $1 AND customer_id = $2",
                doc_id, customer_id
            )
            if not doc:
                raise HTTPException(404, "Document not found")

            # Keys in this document
            this_content = doc["content"] or {}
            this_text = _json.dumps(this_content) if isinstance(this_content, dict) else str(this_content)
            this_keys = set(m.group(1).strip() for m in _re.finditer(r'\{\{([^}]+)\}\}', this_text))

            # Keys still present in ALL OTHER documents in the same plan
            other_docs = await conn.fetch(
                f"SELECT content FROM {settings.DATABASE_APP_SCHEMA}.customer_documents "
                f"WHERE customer_id = $1 AND plan_id = $2 AND id != $3",
                customer_id, doc["plan_id"], doc_id
            )
            survivor_keys: set = set()
            for od in other_docs:
                if od["content"]:
                    text = _json.dumps(od["content"]) if isinstance(od["content"], dict) else str(od["content"])
                    for m in _re.finditer(r'\{\{([^}]+)\}\}', text):
                        survivor_keys.add(m.group(1).strip())

            # Orphaned keys = in this doc, not in any other doc
            orphaned = list(this_keys - survivor_keys)

            # Find active tasks that would be cancelled
            tasks = await conn.fetch(f"""
                SELECT id, title, status, priority, requires_evidence
                FROM {settings.DATABASE_APP_SCHEMA}.customer_tasks
                WHERE customer_id = $1 AND plan_id = $2
                  AND auto_generated = true
                  AND placeholder_key = ANY($3::text[])
                  AND status NOT IN ('completed', 'cancelled')
                ORDER BY
                  CASE status
                    WHEN 'in_progress' THEN 1
                    WHEN 'on_hold' THEN 2
                    WHEN 'pending' THEN 3
                    ELSE 4
                  END, title
            """, customer_id, doc["plan_id"], orphaned) if orphaned else []

        non_pending = [dict(t) for t in tasks if t["status"] not in ("pending", "cancelled")]
        pending_count = sum(1 for t in tasks if t["status"] == "pending")
        return {
            "document_name": doc["document_name"],
            "total_tasks": len(tasks),
            "pending_count": pending_count,
            "non_pending_tasks": [
                {"id": str(t["id"]), "title": t["title"], "status": t["status"],
                 "priority": t["priority"], "requires_evidence": t["requires_evidence"]}
                for t in non_pending
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task impact for doc {doc_id}: {e}")
        raise HTTPException(500, str(e))


@router.delete("/{customer_id}/documents/{doc_id}")
async def delete_customer_document(
    customer_id: int,
    doc_id: UUID,
    current_user: dict = Depends(require_operator)
):
    """
    Delete a customer document, then run plan-wide task sync.
    After deletion, any placeholder that no longer appears in any surviving
    document in the plan has its auto-generated tasks cancelled.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            doc = await conn.fetchrow(
                f"SELECT id, plan_id, document_name FROM {settings.DATABASE_APP_SCHEMA}.customer_documents "
                f"WHERE id = $1 AND customer_id = $2",
                doc_id, customer_id
            )
            if not doc:
                raise HTTPException(404, "Document not found")

            plan_id = doc["plan_id"]

            # Delete the document first, then sync so the scan sees remaining docs
            await conn.execute(
                f"DELETE FROM {settings.DATABASE_APP_SCHEMA}.customer_documents WHERE id = $1",
                doc_id
            )

            # Full reconciliation: seed new keys, reactivate returned, cancel removed
            sync = await reconcile_plan(conn, customer_id, plan_id)

        logger.info(
            f"Document {doc_id} ({doc['document_name']}) deleted by user {current_user.get('user_id')}: "
            f"cancelled={sync['cancelled']} reactivated={sync['reactivated']} active_keys={sync['active_keys']}"
        )
        return {
            "deleted": True,
            "document_name": doc["document_name"],
            "tasks_cancelled": sync["cancelled"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        raise HTTPException(500, str(e))


@router.post("/{customer_id}/reset-password", response_model=PortalCredentials)
async def reset_portal_password(
    customer_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    Reset portal password for customer.

    Returns:
        New portal credentials
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if exists
            customer = await conn.fetchrow(
                f"SELECT id, name, portal_username, portal_enabled FROM {settings.DATABASE_APP_SCHEMA}.customers WHERE id = $1",
                customer_id
            )
            if not customer:
                raise HTTPException(404, f"Customer {customer_id} not found")

            if not customer['portal_enabled']:
                raise HTTPException(400, "Portal is not enabled for this customer")

            # Generate new password
            new_password = generate_password(16)
            password_hash = hash_password(new_password)

            # Update password
            await conn.execute(
                f"UPDATE {settings.DATABASE_APP_SCHEMA}.customers SET portal_password_hash = $1, updated_at = NOW() WHERE id = $2",
                password_hash, customer_id
            )

            logger.info(f"Reset portal password for customer {customer_id} by user {current_user.get('user_id')}")

            return PortalCredentials(
                username=customer['portal_username'],
                password=new_password,
                customer_id=customer_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password for customer {customer_id}: {e}")
        raise HTTPException(500, f"Failed to reset password: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Customer Portal endpoints
# ─────────────────────────────────────────────────────────────

import os as _os

def _portal_url(token: str) -> str:
    base = _os.getenv("PORTAL_URL", "http://localhost:4000").rstrip("/")
    return f"{base}/auth?token={token}"


@router.get("/{customer_id}/portal")
async def get_customer_portal(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Return portal access info + activity log for a customer."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        access = await conn.fetchrow(
            f"""SELECT token, expires_at, last_used_at, created_at
                FROM {settings.DATABASE_APP_SCHEMA}.customer_portal_access
                WHERE customer_id = $1""",
            customer_id,
        )
        activity = await conn.fetch(
            f"""SELECT event, detail, ip_address, created_at
                FROM {settings.DATABASE_APP_SCHEMA}.portal_activity_log
                WHERE customer_id = $1
                ORDER BY created_at DESC LIMIT 50""",
            customer_id,
        )

    if not access:
        return {"has_access": False, "activity": []}

    from datetime import datetime, timezone
    expires = access["expires_at"]
    is_active = expires > datetime.utcnow() if expires else False

    return {
        "has_access": True,
        "portal_url": _portal_url(access["token"]),
        "token": access["token"],
        "expires_at": access["expires_at"].isoformat() if access["expires_at"] else None,
        "last_used_at": access["last_used_at"].isoformat() if access["last_used_at"] else None,
        "created_at": access["created_at"].isoformat() if access["created_at"] else None,
        "is_active": is_active,
        "activity": [
            {
                "event": r["event"],
                "detail": r["detail"] or {},
                "ip_address": r["ip_address"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in activity
        ],
    }


@router.post("/{customer_id}/portal/regenerate")
async def regenerate_portal_token(
    customer_id: int,
    current_user: dict = Depends(require_operator),
):
    """Generate a new portal access token for the customer (invalidates old one)."""
    import secrets
    new_token = secrets.token_hex(32)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            f"SELECT id FROM {settings.DATABASE_APP_SCHEMA}.customer_portal_access WHERE customer_id = $1",
            customer_id,
        )
        if existing:
            row = await conn.fetchrow(
                f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customer_portal_access
                    SET token = $1, expires_at = NOW() + INTERVAL '1 year',
                        last_used_at = NULL, created_at = NOW()
                    WHERE customer_id = $2
                    RETURNING token, expires_at""",
                new_token, customer_id,
            )
        else:
            row = await conn.fetchrow(
                f"""INSERT INTO {settings.DATABASE_APP_SCHEMA}.customer_portal_access
                        (customer_id, token, expires_at)
                    VALUES ($1, $2, NOW() + INTERVAL '1 year')
                    RETURNING token, expires_at""",
                customer_id, new_token,
            )
    return {
        "portal_url": _portal_url(row["token"]),
        "token": row["token"],
        "expires_at": row["expires_at"].isoformat(),
    }


# ── LLM Usage per customer ──────────────────────────────────────────────────

class BudgetUpdate(BaseModel):
    monthly_llm_budget_usd: Optional[float] = None   # None = remove limit


@router.get("/{customer_id}/usage")
async def get_customer_usage(
    customer_id: int,
    current_user: dict = Depends(require_operator),
):
    """Return LLM usage + budget for one customer (current month + all-time)."""
    schema = settings.DATABASE_APP_SCHEMA
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Budget
        budget_row = await conn.fetchrow(
            f"SELECT monthly_llm_budget_usd FROM {schema}.customers WHERE id = $1",
            customer_id,
        )
        if not budget_row:
            raise HTTPException(404, "Customer not found")

        # This-month summary
        summary = await conn.fetchrow(
            f"""SELECT
                    COALESCE(SUM(cost_usd), 0)              AS month_cost,
                    COALESCE(SUM(tokens_input), 0)          AS month_tokens_in,
                    COALESCE(SUM(tokens_output), 0)         AS month_tokens_out,
                    COUNT(*)                                AS month_calls
                FROM {schema}.ai_usage_log
                WHERE customer_id = $1
                  AND started_at >= date_trunc('month', NOW())""",
            customer_id,
        )

        # All-time total
        total = await conn.fetchrow(
            f"""SELECT
                    COALESCE(SUM(cost_usd), 0)      AS total_cost,
                    COALESCE(SUM(tokens_input), 0)  AS total_tokens_in,
                    COALESCE(SUM(tokens_output), 0) AS total_tokens_out,
                    COUNT(*)                        AS total_calls
                FROM {schema}.ai_usage_log
                WHERE customer_id = $1""",
            customer_id,
        )

        # This-month breakdown by operation
        rows = await conn.fetch(
            f"""SELECT operation_type, provider, model,
                       COUNT(*) AS calls,
                       COALESCE(SUM(tokens_input), 0)  AS tokens_input,
                       COALESCE(SUM(tokens_output), 0) AS tokens_output,
                       COALESCE(SUM(cost_usd), 0)      AS cost_usd
                FROM {schema}.ai_usage_log
                WHERE customer_id = $1
                  AND started_at >= date_trunc('month', NOW())
                GROUP BY operation_type, provider, model
                ORDER BY cost_usd DESC""",
            customer_id,
        )

        # Recent calls (last 20)
        recent = await conn.fetch(
            f"""SELECT operation_type, provider, model,
                       tokens_input, tokens_output, cost_usd, started_at
                FROM {schema}.ai_usage_log
                WHERE customer_id = $1
                ORDER BY started_at DESC LIMIT 20""",
            customer_id,
        )

    budget = float(budget_row["monthly_llm_budget_usd"]) if budget_row["monthly_llm_budget_usd"] else None
    month_cost = float(summary["month_cost"])

    return {
        "budget": budget,
        "budget_used_pct": round(month_cost / budget * 100, 1) if budget else None,
        "this_month": {
            "cost_usd":    float(summary["month_cost"]),
            "tokens_in":   int(summary["month_tokens_in"]),
            "tokens_out":  int(summary["month_tokens_out"]),
            "calls":       int(summary["month_calls"]),
        },
        "all_time": {
            "cost_usd":    float(total["total_cost"]),
            "tokens_in":   int(total["total_tokens_in"]),
            "tokens_out":  int(total["total_tokens_out"]),
            "calls":       int(total["total_calls"]),
        },
        "breakdown": [
            {
                "operation_type": r["operation_type"],
                "provider": r["provider"],
                "model": r["model"],
                "calls": int(r["calls"]),
                "tokens_input": int(r["tokens_input"]),
                "tokens_output": int(r["tokens_output"]),
                "cost_usd": float(r["cost_usd"]),
            }
            for r in rows
        ],
        "recent": [
            {
                "operation_type": r["operation_type"],
                "provider": r["provider"],
                "model": r["model"],
                "tokens_input": int(r["tokens_input"]),
                "tokens_output": int(r["tokens_output"]),
                "cost_usd": float(r["cost_usd"]),
                "started_at": r["started_at"].isoformat(),
            }
            for r in recent
        ],
    }


@router.put("/{customer_id}/budget")
async def update_customer_budget(
    customer_id: int,
    body: BudgetUpdate,
    current_user: dict = Depends(require_operator),
):
    """Set or clear a customer's monthly LLM budget."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""UPDATE {settings.DATABASE_APP_SCHEMA}.customers
                SET monthly_llm_budget_usd = $1
                WHERE id = $2
                RETURNING id, monthly_llm_budget_usd""",
            body.monthly_llm_budget_usd, customer_id,
        )
    if not row:
        raise HTTPException(404, "Customer not found")
    return {
        "monthly_llm_budget_usd": float(row["monthly_llm_budget_usd"]) if row["monthly_llm_budget_usd"] else None
    }
