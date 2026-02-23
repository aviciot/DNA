"""
ISO Customer Management API
============================

Enhanced customer management with portal credentials, storage, and ISO assignment.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime, date

from ..database import get_db_pool
from ..auth import get_current_user, require_admin
from ..config import settings
from ..services.storage_service import storage_service
from ..utils.credentials import generate_portal_credentials

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
    email: str = Field(..., description="Primary email")
    contact_email: Optional[str] = Field(None, description="Contact email for communication")
    document_email: Optional[str] = Field(None, description="Email for documents")

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
    email: Optional[str] = None
    contact_email: Optional[str] = None
    document_email: Optional[str] = None
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
    current_user: dict = Depends(require_admin)
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
                    from ..utils.credentials import hash_password
                    portal_password_hash = hash_password(portal_password)

            # Set contact and document emails (default to primary email)
            contact_email = customer_data.contact_email or customer_data.email
            document_email = customer_data.document_email or customer_data.email

            # Create customer record
            customer_row = await conn.fetchrow(f"""
                INSERT INTO {settings.DATABASE_APP_SCHEMA}.customers (
                    name, contact_person, phone, address, email,
                    contact_email, document_email, status,
                    portal_username, portal_password_hash, portal_enabled,
                    storage_type,
                    created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id, name, contact_person, phone, address, email,
                          contact_email, document_email, status,
                          portal_username, portal_enabled, last_portal_login,
                          storage_type, storage_path,
                          created_by, created_at, updated_at
            """, customer_data.name, customer_data.contact_person, customer_data.phone,
                customer_data.address, customer_data.email, contact_email, document_email,
                'active', portal_username, portal_password_hash, customer_data.portal_enabled,
                customer_data.storage_type, current_user.get('user_id'))

            customer = dict(customer_row)
            customer_id = customer['id']

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

            # Build response
            response = {
                "customer": customer,
                "portal_credentials": None
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
    current_user: dict = Depends(require_admin)
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

            for field in ["name", "contact_person", "phone", "address", "email",
                         "contact_email", "document_email", "portal_enabled"]:
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
            from ..utils.credentials import generate_password, hash_password
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
