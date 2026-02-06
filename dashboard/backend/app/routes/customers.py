"""
DNA Backend - Customer Routes
==============================
Customer management endpoints.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from ..models import (
    Customer, CustomerCreate, CustomerUpdate,
    CustomerCertification, CustomerCertificationDetail
)
from ..database import get_db_pool
from ..auth import get_current_user, require_admin
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[Customer])
async def list_customers(current_user = Depends(get_current_user)):
    """List all customers."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT id, name, email, secondary_email, phone, address, 
                       business_area, notes, created_by, created_at, updated_at
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers
                ORDER BY name ASC
            """)
            return [Customer(**dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        raise HTTPException(500, "Failed to retrieve customers")


@router.get("/{customer_id}", response_model=Customer)
async def get_customer(customer_id: int, current_user = Depends(get_current_user)):
    """Get customer by ID."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT id, name, email, secondary_email, phone, address,
                       business_area, notes, created_by, created_at, updated_at
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers
                WHERE id = $1
            """, customer_id)
            
            if not row:
                raise HTTPException(404, "Customer not found")
            
            return Customer(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer: {e}")
        raise HTTPException(500, "Failed to retrieve customer")


@router.post("", response_model=Customer, status_code=201)
async def create_customer(customer: CustomerCreate, current_user = Depends(require_admin)):
    """Create new customer (admin only)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if email exists
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers WHERE email = $1",
                customer.email
            )
            if existing:
                raise HTTPException(400, "Customer with this email already exists")
            
            row = await conn.fetchrow(f"""
                INSERT INTO {settings.DATABASE_CUSTOMER_SCHEMA}.customers 
                (name, email, secondary_email, phone, address, business_area, notes, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, name, email, secondary_email, phone, address,
                          business_area, notes, created_by, created_at, updated_at
            """, customer.name, customer.email, customer.secondary_email, customer.phone,
                customer.address, customer.business_area, customer.notes, current_user["user_id"])
            
            return Customer(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(500, "Failed to create customer")


@router.put("/{customer_id}", response_model=Customer)
async def update_customer(
    customer_id: int, 
    customer: CustomerUpdate, 
    current_user = Depends(require_admin)
):
    """Update customer (admin only)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if customer exists
            existing = await conn.fetchrow(
                f"SELECT id FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers WHERE id = $1",
                customer_id
            )
            if not existing:
                raise HTTPException(404, "Customer not found")
            
            # Check email uniqueness if being updated
            if customer.email:
                email_exists = await conn.fetchrow(
                    f"SELECT id FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers WHERE email = $1 AND id != $2",
                    customer.email, customer_id
                )
                if email_exists:
                    raise HTTPException(400, "Email already in use by another customer")
            
            # Build dynamic update
            updates = []
            params = []
            param_count = 1
            
            for field in ["name", "email", "secondary_email", "phone", "address", "business_area", "notes"]:
                value = getattr(customer, field, None)
                if value is not None:
                    updates.append(f"{field} = ${param_count}")
                    params.append(value)
                    param_count += 1
            
            if not updates:
                return await get_customer(customer_id, current_user)
            
            params.append(customer_id)
            query = f"""
                UPDATE {settings.DATABASE_CUSTOMER_SCHEMA}.customers
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, name, email, secondary_email, phone, address,
                          business_area, notes, created_by, created_at, updated_at
            """
            
            row = await conn.fetchrow(query, *params)
            return Customer(**dict(row))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer: {e}")
        raise HTTPException(500, "Failed to update customer")


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: int, current_user = Depends(require_admin)):
    """Delete customer (admin only)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers WHERE id = $1",
                customer_id
            )
            
            if result.split()[-1] == "0":
                raise HTTPException(404, "Customer not found")
            
            return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer: {e}")
        raise HTTPException(500, "Failed to delete customer")


@router.get("/{customer_id}/certifications", response_model=List[CustomerCertificationDetail])
async def get_customer_certifications(customer_id: int, current_user = Depends(get_current_user)):
    """Get all certifications for a customer with progress."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT 
                    cc.id, cc.customer_id, cc.certification_id, cc.status,
                    cc.progress_percentage, cc.start_date, cc.target_completion_date,
                    cc.actual_completion_date, cc.assigned_to, cc.notes,
                    cc.created_at, cc.updated_at,
                    cert.id as cert_id, cert.code, cert.name, cert.description,
                    cert.requirements_count, cert.created_at as cert_created_at,
                    cust.id as cust_id, cust.name as cust_name, cust.email,
                    COUNT(cd.id) as documents_count,
                    COUNT(CASE WHEN cd.status = 'approved' THEN 1 END) as completed_documents
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customer_certifications cc
                JOIN {settings.DATABASE_CUSTOMER_SCHEMA}.certifications cert ON cc.certification_id = cert.id
                JOIN {settings.DATABASE_CUSTOMER_SCHEMA}.customers cust ON cc.customer_id = cust.id
                LEFT JOIN {settings.DATABASE_CUSTOMER_SCHEMA}.customer_documents cd ON cc.id = cd.customer_certification_id
                WHERE cc.customer_id = $1
                GROUP BY cc.id, cert.id, cert.code, cert.name, cert.description,
                         cert.requirements_count, cert.created_at, 
                         cust.id, cust.name, cust.email
                ORDER BY cc.created_at DESC
            """, customer_id)
            
            result = []
            for row in rows:
                cert_data = CustomerCertification(**{
                    "id": row["id"],
                    "customer_id": row["customer_id"],
                    "certification_id": row["certification_id"],
                    "status": row["status"],
                    "progress_percentage": row["progress_percentage"],
                    "start_date": row["start_date"],
                    "target_completion_date": row["target_completion_date"],
                    "actual_completion_date": row["actual_completion_date"],
                    "assigned_to": row["assigned_to"],
                    "notes": row["notes"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
                
                # Add related data
                from models import Certification, Customer
                result.append(CustomerCertificationDetail(
                    **cert_data.dict(),
                    certification=Certification(
                        id=row["cert_id"],
                        code=row["code"],
                        name=row["name"],
                        description=row["description"],
                        requirements_count=row["requirements_count"],
                        created_at=row["cert_created_at"],
                        updated_at=row["cert_created_at"]
                    ),
                    customer=Customer(
                        id=row["cust_id"],
                        name=row["cust_name"],
                        email=row["email"],
                        secondary_email=None,
                        phone=None,
                        address=None,
                        business_area=None,
                        notes=None,
                        created_by=None,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"]
                    ),
                    documents_count=row["documents_count"],
                    completed_documents=row["completed_documents"]
                ))
            
            return result
            
    except Exception as e:
        logger.error(f"Error getting customer certifications: {e}")
        raise HTTPException(500, "Failed to retrieve customer certifications")
