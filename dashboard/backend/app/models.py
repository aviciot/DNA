"""
DNA Backend - Pydantic Models
==============================
Data models for customers, certifications, and templates.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator
import re


class CustomerBase(BaseModel):
    """Base customer model."""
    name: str
    email: EmailStr
    secondary_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    business_area: Optional[str] = None
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    """Customer creation request."""
    pass


class CustomerUpdate(BaseModel):
    """Customer update request."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    secondary_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    business_area: Optional[str] = None
    notes: Optional[str] = None


class Customer(CustomerBase):
    """Customer response model."""
    id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CertificationBase(BaseModel):
    """Base certification model."""
    code: str
    name: str
    description: Optional[str] = None
    requirements_count: int = 0


class Certification(CertificationBase):
    """Certification response model."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateFieldMetadata(BaseModel):
    """Metadata for a single template field."""
    name: str
    type: str  # text, date, number, email, phone, address, textarea, select
    required: bool = False
    description: Optional[str] = None
    example: Optional[str] = None
    options: Optional[List[str]] = None  # For select fields


class CertificationTemplateCreate(BaseModel):
    """Template creation request."""
    certification_id: int
    name: str
    description: Optional[str] = None
    document_type: str  # policy, procedure, form, checklist


class CertificationTemplate(BaseModel):
    """Certification template response."""
    id: int
    certification_id: int
    name: str
    description: Optional[str]
    document_type: str
    template_structure: Dict[str, Any]
    fields_metadata: List[Dict[str, Any]]
    original_filename: Optional[str]
    file_url: Optional[str]
    version: int
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerCertificationCreate(BaseModel):
    """Customer certification assignment."""
    customer_id: int
    certification_id: int
    start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class CustomerCertificationUpdate(BaseModel):
    """Customer certification update."""
    status: Optional[str] = None
    progress_percentage: Optional[float] = None
    start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    actual_completion_date: Optional[date] = None
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class CustomerCertification(BaseModel):
    """Customer certification response."""
    id: int
    customer_id: int
    certification_id: int
    status: str
    progress_percentage: float
    start_date: Optional[date]
    target_completion_date: Optional[date]
    actual_completion_date: Optional[date]
    assigned_to: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerCertificationDetail(CustomerCertification):
    """Customer certification with related data."""
    certification: Certification
    customer: Customer
    documents_count: int = 0
    completed_documents: int = 0


class CustomerDocumentCreate(BaseModel):
    """Customer document creation."""
    customer_certification_id: int
    template_id: int
    document_name: str
    filled_data: Dict[str, Any] = {}
    assigned_to: Optional[int] = None


class CustomerDocumentUpdate(BaseModel):
    """Customer document update."""
    filled_data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    completion_percentage: Optional[float] = None
    assigned_to: Optional[int] = None
    reviewed_by: Optional[int] = None
    notes: Optional[str] = None


class CustomerDocument(BaseModel):
    """Customer document response."""
    id: int
    customer_certification_id: int
    template_id: int
    document_name: str
    filled_data: Dict[str, Any]
    status: str
    completion_percentage: float
    assigned_to: Optional[int]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    notes: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerDocumentDetail(CustomerDocument):
    """Customer document with template info."""
    template: CertificationTemplate


class TemplateUploadResponse(BaseModel):
    """Response after uploading and parsing a template."""
    template_id: int
    name: str
    fields_count: int
    required_fields_count: int
    document_type: str
    fields: List[Dict[str, Any]]


class CustomerProgress(BaseModel):
    """Customer certification progress summary."""
    customer_id: int
    customer_name: str
    certification_id: int
    certification_name: str
    status: str
    progress_percentage: float
    total_documents: int
    completed_documents: int
    in_progress_documents: int
    pending_documents: int
    target_date: Optional[date]
    days_remaining: Optional[int]
