"""
Phase 3B: Customer Management API
==================================
Enhanced customer CRUD with welcome emails and plan management
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
import asyncpg

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/customers", tags=["Customer Management"])


# =====================================================
# Pydantic Models
# =====================================================

class CustomerCreate(BaseModel):
    """Customer creation request."""
    name: str
    email: EmailStr
    contact_person: str
    phone: str
    website: Optional[str] = None
    compliance_email: Optional[str] = None  # For document automation
    contract_email: Optional[str] = None     # For CISO/Legal
    address: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"

    # Welcome email configuration (optional)
    send_welcome_email: bool = False
    welcome_email_config_key: Optional[str] = "default_welcome"
    welcome_email_schedule: str = "immediate"  # "immediate" or "after_plan_setup"


class CustomerUpdate(BaseModel):
    """Customer update request."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    compliance_email: Optional[str] = None
    contract_email: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class CustomerResponse(BaseModel):
    """Customer response."""
    id: int
    name: str
    email: str
    website: Optional[str]
    compliance_email: Optional[str]
    contract_email: Optional[str]
    contact_person: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    # Statistics
    total_plans: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    overall_progress: int = 0


class CustomerListResponse(BaseModel):
    """Customer list response."""
    customers: List[CustomerResponse]
    total: int
    page: int
    page_size: int


# =====================================================
# Endpoints
# =====================================================

@router.post("/", response_model=CustomerResponse)
async def create_customer(
    customer: CustomerCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a new customer.

    Optionally sends welcome email based on configuration.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Create customer
                customer_row = await conn.fetchrow("""
                    INSERT INTO dna_app.customers (
                        name, email, website, compliance_email, contract_email,
                        contact_person, phone, address, description, status, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING id, name, email, website, compliance_email, contract_email,
                              contact_person, phone, address, description, status, created_at, updated_at
                """, customer.name, customer.email, customer.website,
                    customer.compliance_email, customer.contract_email,
                    customer.contact_person, customer.phone, customer.address,
                    customer.description, customer.status, user.get("user_id"))

                customer_id = customer_row['id']

                # TODO: Send welcome email if requested
                # if customer.send_welcome_email:
                #     await send_welcome_email(
                #         customer_id,
                #         customer.welcome_email_config_key,
                #         customer.welcome_email_schedule
                #     )

                logger.info(f"Customer created: {customer_id} by user {user.get('user_id')}")

                return CustomerResponse(
                    id=customer_row['id'],
                    name=customer_row['name'],
                    email=customer_row['email'],
                    website=customer_row['website'],
                    compliance_email=customer_row['compliance_email'],
                    contract_email=customer_row['contract_email'],
                    contact_person=customer_row['contact_person'],
                    phone=customer_row['phone'],
                    address=customer_row['address'],
                    description=customer_row['description'],
                    status=customer_row['status'],
                    created_at=customer_row['created_at'],
                    updated_at=customer_row['updated_at'],
                    total_plans=0,
                    active_tasks=0,
                    completed_tasks=0,
                    overall_progress=0
                )

    except asyncpg.UniqueViolationError:
        raise HTTPException(400, "Customer with this email already exists")
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(500, f"Failed to create customer: {str(e)}")


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    """
    List all customers with pagination and filters.
    """
    pool = await get_db_pool()
    offset = (page - 1) * page_size

    try:
        async with pool.acquire() as conn:
            # Build query with filters
            where_clauses = []
            params = []
            param_idx = 1

            if status:
                where_clauses.append(f"c.status = ${param_idx}")
                params.append(status)
                param_idx += 1

            if search:
                where_clauses.append(f"(c.name ILIKE ${param_idx} OR c.email ILIKE ${param_idx})")
                params.append(f"%{search}%")
                param_idx += 1

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Get total count
            total = await conn.fetchval(f"""
                SELECT COUNT(*) FROM dna_app.customers c {where_sql}
            """, *params)

            # Get customers with statistics
            params.extend([page_size, offset])
            rows = await conn.fetch(f"""
                SELECT
                    c.id, c.name, c.email, c.website, c.compliance_email, c.contract_email,
                    c.contact_person, c.phone, c.address, c.description,
                    c.status, c.created_at, c.updated_at,

                    -- Statistics
                    COUNT(DISTINCT cip.id) FILTER (WHERE cip.is_ignored = false OR cip.is_ignored IS NULL) as total_plans,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status IN ('pending', 'in_progress') AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as active_tasks,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as completed_tasks,

                    -- Overall progress
                    CASE
                        WHEN COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL) = 0 THEN 0
                        ELSE (COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL))::float /
                              COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL)::float * 100)::int
                    END as overall_progress

                FROM dna_app.customers c
                LEFT JOIN dna_app.customer_iso_plans cip ON c.id = cip.customer_id
                LEFT JOIN dna_app.customer_tasks ct ON c.id = ct.customer_id
                {where_sql}
                GROUP BY c.id, c.name, c.email, c.website, c.compliance_email, c.contract_email,
                         c.contact_person, c.phone, c.address, c.description,
                         c.status, c.created_at, c.updated_at
                ORDER BY c.created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """, *params)

            customers = [
                CustomerResponse(
                    id=row['id'],
                    name=row['name'],
                    email=row['email'],
                    website=row['website'],
                    compliance_email=row['compliance_email'],
                    contract_email=row['contract_email'],
                    contact_person=row['contact_person'],
                    phone=row['phone'],
                    address=row['address'],
                    description=row['description'],
                    status=row['status'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    total_plans=row['total_plans'],
                    active_tasks=row['active_tasks'],
                    completed_tasks=row['completed_tasks'],
                    overall_progress=row['overall_progress']
                )
                for row in rows
            ]

            return CustomerListResponse(
                customers=customers,
                total=total,
                page=page,
                page_size=page_size
            )

    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        raise HTTPException(500, f"Failed to list customers: {str(e)}")


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Get customer details by ID.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    c.id, c.name, c.email, c.website, c.compliance_email, c.contract_email,
                    c.contact_person, c.phone, c.address, c.description,
                    c.status, c.created_at, c.updated_at,

                    -- Statistics
                    COUNT(DISTINCT cip.id) FILTER (WHERE cip.is_ignored = false OR cip.is_ignored IS NULL) as total_plans,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status IN ('pending', 'in_progress') AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as active_tasks,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as completed_tasks,

                    -- Overall progress
                    CASE
                        WHEN COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL) = 0 THEN 0
                        ELSE (COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL))::float /
                              COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL)::float * 100)::int
                    END as overall_progress

                FROM dna_app.customers c
                LEFT JOIN dna_app.customer_iso_plans cip ON c.id = cip.customer_id
                LEFT JOIN dna_app.customer_tasks ct ON c.id = ct.customer_id
                WHERE c.id = $1
                GROUP BY c.id, c.name, c.email, c.website, c.compliance_email, c.contract_email,
                         c.contact_person, c.phone, c.address, c.description,
                         c.status, c.created_at, c.updated_at
            """, customer_id)

            if not row:
                raise HTTPException(404, "Customer not found")

            return CustomerResponse(
                id=row['id'],
                name=row['name'],
                email=row['email'],
                website=row['website'],
                compliance_email=row['compliance_email'],
                contract_email=row['contract_email'],
                contact_person=row['contact_person'],
                phone=row['phone'],
                address=row['address'],
                description=row['description'],
                status=row['status'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                total_plans=row['total_plans'],
                active_tasks=row['active_tasks'],
                completed_tasks=row['completed_tasks'],
                overall_progress=row['overall_progress']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer: {e}")
        raise HTTPException(500, f"Failed to get customer: {str(e)}")


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    updates: CustomerUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update customer details.
    """
    pool = await get_db_pool()

    # Build update query dynamically
    update_fields = []
    params = []
    param_idx = 1

    for field, value in updates.dict(exclude_unset=True).items():
        if value is not None:
            update_fields.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not update_fields:
        raise HTTPException(400, "No fields to update")

    params.append(customer_id)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                UPDATE dna_app.customers
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE id = ${param_idx}
                RETURNING id, name, email, website, compliance_email, contract_email,
                          contact_person, phone, address, description,
                          status, created_at, updated_at
            """, *params)

            if not row:
                raise HTTPException(404, "Customer not found")

            logger.info(f"Customer updated: {customer_id} by user {user.get('user_id')}")

            # Get statistics
            stats_row = await conn.fetchrow("""
                SELECT
                    COUNT(DISTINCT cip.id) FILTER (WHERE cip.is_ignored = false OR cip.is_ignored IS NULL) as total_plans,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status IN ('pending', 'in_progress') AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as active_tasks,
                    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL)) as completed_tasks,
                    CASE
                        WHEN COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL) = 0 THEN 0
                        ELSE (COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND (ct.is_ignored = false OR ct.is_ignored IS NULL))::float /
                              COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false OR ct.is_ignored IS NULL)::float * 100)::int
                    END as overall_progress
                FROM dna_app.customer_iso_plans cip
                LEFT JOIN dna_app.customer_tasks ct ON cip.customer_id = ct.customer_id
                WHERE cip.customer_id = $1
            """, customer_id)

            return CustomerResponse(
                id=row['id'],
                name=row['name'],
                email=row['email'],
                website=row['website'],
                compliance_email=row['compliance_email'],
                contract_email=row['contract_email'],
                contact_person=row['contact_person'],
                phone=row['phone'],
                address=row['address'],
                description=row['description'],
                status=row['status'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                total_plans=stats_row['total_plans'] if stats_row else 0,
                active_tasks=stats_row['active_tasks'] if stats_row else 0,
                completed_tasks=stats_row['completed_tasks'] if stats_row else 0,
                overall_progress=stats_row['overall_progress'] if stats_row else 0
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer: {e}")
        raise HTTPException(500, f"Failed to update customer: {str(e)}")


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    soft_delete: bool = Query(True, description="Soft delete (set status=inactive) or hard delete"),
    user: dict = Depends(get_current_user)
):
    """
    Delete customer (soft delete by default, sets status to inactive).
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            if soft_delete:
                # Soft delete - set status to inactive
                result = await conn.fetchval("""
                    UPDATE dna_app.customers
                    SET status = 'inactive', updated_at = NOW()
                    WHERE id = $1
                    RETURNING id
                """, customer_id)

                if not result:
                    raise HTTPException(404, "Customer not found")

                logger.info(f"Customer soft deleted: {customer_id} by user {user.get('user_id')}")
                return {"message": "Customer deactivated successfully", "customer_id": customer_id}
            else:
                # Hard delete
                result = await conn.fetchval("""
                    DELETE FROM dna_app.customers
                    WHERE id = $1
                    RETURNING id
                """, customer_id)

                if not result:
                    raise HTTPException(404, "Customer not found")

                logger.info(f"Customer hard deleted: {customer_id} by user {user.get('user_id')}")
                return {"message": "Customer deleted successfully", "customer_id": customer_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer: {e}")
        raise HTTPException(500, f"Failed to delete customer: {str(e)}")
