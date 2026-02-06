"""
DNA Backend - Template Routes
==============================
Template upload, parsing, and management endpoints.
"""

import logging
import os
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from datetime import datetime

from ..models import (
    CertificationTemplate, CertificationTemplateCreate,
    TemplateUploadResponse, Certification, CustomerDocumentDetail
)
from ..database import get_db_pool
from ..auth import get_current_user, require_admin
from ..services.template_parser import TemplateParser
from ..services.document_generator import IntelligentDocumentGenerator
from ..services import task_service
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = "/tmp/dna_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=List[CertificationTemplate])
async def list_templates(
    certification_id: int = None,
    current_user = Depends(get_current_user)
):
    """List all templates, optionally filtered by certification."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if certification_id:
                rows = await conn.fetch(f"""
                    SELECT id, certification_id, name, description, document_type,
                           template_structure, fields_metadata, original_filename,
                           file_url, version, is_active, created_by, created_at, updated_at
                    FROM {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                    WHERE certification_id = $1 AND is_active = true
                    ORDER BY name ASC
                """, certification_id)
            else:
                rows = await conn.fetch(f"""
                    SELECT id, certification_id, name, description, document_type,
                           template_structure, fields_metadata, original_filename,
                           file_url, version, is_active, created_by, created_at, updated_at
                    FROM {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                    WHERE is_active = true
                    ORDER BY certification_id, name ASC
                """)
            
            return [CertificationTemplate(**dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(500, "Failed to retrieve templates")


@router.post("/upload", response_model=TemplateUploadResponse, status_code=201)
async def upload_and_parse_template(
    certification_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(require_admin)
):
    """
    Upload Word document and parse it with AI to create template.
    
    Steps:
    1. Save uploaded .docx file
    2. Extract text using python-docx
    3. Parse with Claude to identify fillable fields
    4. Store template in database
    5. Return parsed results
    """
    try:
        # Validate file type
        if not file.filename.endswith('.docx'):
            raise HTTPException(400, "Only .docx files are supported")
        
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Saved uploaded file: {file_path}")
        
        # Parse template with AI
        parser = TemplateParser()
        parsed_result = parser.parse_document_template(file_path, name)
        
        # Store in database
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                INSERT INTO {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                (certification_id, name, description, document_type, template_structure,
                 fields_metadata, original_filename, file_url, version, is_active, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, true, $9)
                RETURNING id
            """, certification_id, name, description, document_type,
                parsed_result['template_structure'],
                parsed_result['fields_metadata'],
                file.filename,
                file_path,
                current_user["user_id"])
            
            template_id = row['id']
        
        logger.info(f"Template created with ID: {template_id}")
        
        # Return summary
        return TemplateUploadResponse(
            template_id=template_id,
            name=name,
            fields_count=len(parsed_result['fields_metadata']),
            required_fields_count=sum(
                1 for f in parsed_result['fields_metadata'] if f.get('required', False)
            ),
            document_type=document_type,
            fields=parsed_result['fields_metadata']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading and parsing template: {e}")
        raise HTTPException(500, f"Failed to process template: {str(e)}")


@router.post("/upload-async", status_code=202)
async def upload_template_async(
    certification_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(require_admin)
):
    """
    Upload Word document for asynchronous AI parsing (Milestone 1.3)
    
    This endpoint:
    1. Saves the uploaded file
    2. Creates an ai_task record with status 'pending'
    3. Publishes to Redis Stream 'template:parse'
    4. Returns immediately with task_id (HTTP 202 Accepted)
    5. Client can poll GET /api/tasks/{task_id} for progress
    
    Returns:
        task_id, status, and message (HTTP 202 Accepted)
    """
    try:
        # Validate file type
        if not file.filename.endswith('.docx'):
            raise HTTPException(400, "Only .docx files are supported")
        
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Saved uploaded file: {file_path} (async mode)")
        
        # Create template record (placeholder, will be populated by worker)
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                INSERT INTO {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                (certification_id, name, description, document_type, template_structure,
                 fields_metadata, original_filename, file_url, version, is_active, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, false, $9)
                RETURNING id
            """, certification_id, name, description, document_type,
                {},  # Empty structure initially
                [],  # Empty fields initially
                file.filename,
                file_path,
                current_user["user_id"])
            
            template_id = row['id']
        
        # Create task and publish to Redis Stream
        task = await task_service.create_task(
            task_type='template_parse',
            related_id=str(template_id),
            created_by=current_user["user_id"],
            metadata={
                'file_path': file_path,
                'file_name': file.filename,
                'template_name': name,
                'document_type': document_type,
                'certification_id': str(certification_id)
            }
        )
        
        logger.info(f"Created async task {task['id']} for template {template_id}")
        
        return {
            "task_id": task['id'],
            "template_id": template_id,
            "status": "pending",
            "message": f"Template upload accepted. Parsing in progress. Poll GET /api/tasks/{task['id']} for status.",
            "created_at": task['created_at']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading template (async): {e}")
        raise HTTPException(500, f"Failed to process template upload: {str(e)}")


@router.get("/{template_id}", response_model=CertificationTemplate)
async def get_template(template_id: int, current_user = Depends(get_current_user)):
    """Get template by ID."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT id, certification_id, name, description, document_type,
                       template_structure, fields_metadata, original_filename,
                       file_url, version, is_active, created_by, created_at, updated_at
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                WHERE id = $1
            """, template_id)
            
            if not row:
                raise HTTPException(404, "Template not found")
            
            return CertificationTemplate(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {e}")
        raise HTTPException(500, "Failed to retrieve template")


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: int, current_user = Depends(require_admin)):
    """Soft delete template (admin only)."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(f"""
                UPDATE {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                SET is_active = false
                WHERE id = $1
            """, template_id)
            
            if result.split()[-1] == "0":
                raise HTTPException(404, "Template not found")
            
            return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(500, "Failed to delete template")


@router.get("/certifications/{certification_id}/templates", response_model=List[CertificationTemplate])
async def get_templates_by_certification(
    certification_id: int,
    current_user = Depends(get_current_user)
):
    """Get all templates for a specific certification."""
    return await list_templates(certification_id, current_user)


# ============================================================================
# PHASE 2: INTELLIGENT DOCUMENT GENERATION ENDPOINTS
# ============================================================================

@router.post("/documents/generate-from-interview")
async def generate_document_from_interview(
    template_id: int,
    customer_id: int,
    customer_certification_id: int,
    responses: dict,
    current_user = Depends(get_current_user)
):
    """
    Generate document from interview Q&A responses.
    
    Args:
        template_id: The template to fill
        customer_id: The customer this document is for
        customer_certification_id: Link to customer's certification progress
        responses: Dict mapping question IDs to answers
    """
    try:
        pool = await get_db_pool()
        generator = IntelligentDocumentGenerator()
        
        # Get template
        async with pool.acquire() as conn:
            template_row = await conn.fetchrow(f"""
                SELECT id, name, template_structure, fields_metadata
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                WHERE id = $1 AND is_active = true
            """, template_id)
            
            if not template_row:
                raise HTTPException(404, "Template not found")
            
            # Get customer info
            customer_row = await conn.fetchrow(f"""
                SELECT id, name, email, business_area, address, phone
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers
                WHERE id = $1
            """, customer_id)
            
            if not customer_row:
                raise HTTPException(404, "Customer not found")
        
        # Generate document using AI
        customer_info = dict(customer_row)
        filled_data = generator.generate_from_interview(
            template_structure=template_row['template_structure'],
            fields_metadata=template_row['fields_metadata'],
            interview_responses=responses,
            customer_info=customer_info
        )
        
        # Calculate completion
        parser = TemplateParser()
        completion = parser.calculate_document_completion(
            filled_data, template_row['fields_metadata']
        )
        
        # Store document
        async with pool.acquire() as conn:
            doc_id = await conn.fetchval(f"""
                INSERT INTO {settings.DATABASE_CUSTOMER_SCHEMA}.customer_documents
                (customer_certification_id, template_id, filled_data,
                 completion_percentage, status, version, created_by)
                VALUES ($1, $2, $3, $4, $5, 1, $6)
                RETURNING id
            """, customer_certification_id, template_id, filled_data,
                completion, 'draft', current_user["user_id"])
        
        logger.info(f"Generated document {doc_id} from interview for customer {customer_id}")
        
        return {
            "document_id": doc_id,
            "completion_percentage": completion,
            "filled_fields": len([f for f in filled_data.values() if f]),
            "total_fields": len(template_row['fields_metadata']),
            "status": "draft"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating document from interview: {e}")
        raise HTTPException(500, f"Failed to generate document: {str(e)}")


@router.post("/documents/generate-from-text")
async def generate_document_from_text(
    template_id: int,
    customer_id: int,
    customer_certification_id: int,
    description: str,
    current_user = Depends(get_current_user)
):
    """
    Generate document from free-form text description.
    
    Args:
        template_id: The template to fill
        customer_id: The customer this document is for
        customer_certification_id: Link to customer's certification progress
        description: Customer's free-form description of their business/needs
    """
    try:
        pool = await get_db_pool()
        generator = IntelligentDocumentGenerator()
        
        # Get template and customer
        async with pool.acquire() as conn:
            template_row = await conn.fetchrow(f"""
                SELECT id, name, template_structure, fields_metadata
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                WHERE id = $1 AND is_active = true
            """, template_id)
            
            if not template_row:
                raise HTTPException(404, "Template not found")
            
            customer_row = await conn.fetchrow(f"""
                SELECT id, name, email, business_area, address, phone
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers
                WHERE id = $1
            """, customer_id)
            
            if not customer_row:
                raise HTTPException(404, "Customer not found")
        
        # Generate document using AI
        customer_info = dict(customer_row)
        filled_data = generator.generate_from_free_text(
            template_structure=template_row['template_structure'],
            fields_metadata=template_row['fields_metadata'],
            customer_description=description,
            customer_info=customer_info
        )
        
        # Calculate completion
        parser = TemplateParser()
        completion = parser.calculate_document_completion(
            filled_data, template_row['fields_metadata']
        )
        
        # Store document
        async with pool.acquire() as conn:
            doc_id = await conn.fetchval(f"""
                INSERT INTO {settings.DATABASE_CUSTOMER_SCHEMA}.customer_documents
                (customer_certification_id, template_id, filled_data,
                 completion_percentage, status, version, created_by)
                VALUES ($1, $2, $3, $4, $5, 1, $6)
                RETURNING id
            """, customer_certification_id, template_id, filled_data,
                completion, 'draft', current_user["user_id"])
        
        logger.info(f"Generated document {doc_id} from text for customer {customer_id}")
        
        return {
            "document_id": doc_id,
            "completion_percentage": completion,
            "filled_fields": len([f for f in filled_data.values() if f]),
            "total_fields": len(template_row['fields_metadata']),
            "status": "draft"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating document from text: {e}")
        raise HTTPException(500, f"Failed to generate document: {str(e)}")


@router.put("/documents/{document_id}/refine")
async def refine_document(
    document_id: int,
    feedback: str,
    current_user = Depends(get_current_user)
):
    """
    Refine document based on user feedback.
    
    Args:
        document_id: The document to refine
        feedback: User feedback on what to improve/change
    """
    try:
        pool = await get_db_pool()
        generator = IntelligentDocumentGenerator()
        
        # Get current document and template
        async with pool.acquire() as conn:
            doc_row = await conn.fetchrow(f"""
                SELECT cd.id, cd.filled_data, cd.version,
                       ct.template_structure, ct.fields_metadata
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customer_documents cd
                JOIN {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates ct ON cd.template_id = ct.id
                WHERE cd.id = $1
            """, document_id)
            
            if not doc_row:
                raise HTTPException(404, "Document not found")
        
        # Refine using AI
        new_filled_data = generator.refine_document(
            current_filled_data=doc_row['filled_data'],
            fields_metadata=doc_row['fields_metadata'],
            user_feedback=feedback
        )
        
        # Calculate new completion
        parser = TemplateParser()
        completion = parser.calculate_document_completion(
            new_filled_data, doc_row['fields_metadata']
        )
        
        # Update document (create new version)
        async with pool.acquire() as conn:
            await conn.execute(f"""
                UPDATE {settings.DATABASE_CUSTOMER_SCHEMA}.customer_documents
                SET filled_data = $1,
                    completion_percentage = $2,
                    version = version + 1,
                    updated_at = NOW()
                WHERE id = $3
            """, new_filled_data, completion, document_id)
        
        logger.info(f"Refined document {document_id}, new version {doc_row['version'] + 1}")
        
        return {
            "document_id": document_id,
            "version": doc_row['version'] + 1,
            "completion_percentage": completion,
            "filled_fields": len([f for f in new_filled_data.values() if f]),
            "changes_applied": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refining document: {e}")
        raise HTTPException(500, f"Failed to refine document: {str(e)}")


@router.get("/documents/{document_id}/preview")
async def preview_document(
    document_id: int,
    current_user = Depends(get_current_user)
):
    """
    Preview final filled document with all tags replaced.
    
    Returns:
        - Filled document text
        - Completion percentage
        - Missing required fields (if any)
    """
    try:
        pool = await get_db_pool()
        parser = TemplateParser()
        
        # Get document and template
        async with pool.acquire() as conn:
            doc_row = await conn.fetchrow(f"""
                SELECT cd.id, cd.filled_data, cd.completion_percentage,
                       ct.template_structure, ct.fields_metadata, ct.name
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customer_documents cd
                JOIN {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates ct ON cd.template_id = ct.id
                WHERE cd.id = $1
            """, document_id)
            
            if not doc_row:
                raise HTTPException(404, "Document not found")
        
        # Generate filled document
        filled_document = parser.generate_filled_document(
            template_structure=doc_row['template_structure'],
            filled_data=doc_row['filled_data']
        )
        
        # Find missing required fields
        missing_fields = []
        for field in doc_row['fields_metadata']:
            if field.get('required', False):
                field_name = field['name']
                if not doc_row['filled_data'].get(field_name):
                    missing_fields.append({
                        "name": field_name,
                        "label": field.get('label', field_name),
                        "type": field.get('type', 'text')
                    })
        
        return {
            "document_id": document_id,
            "template_name": doc_row['name'],
            "filled_document": filled_document,
            "completion_percentage": doc_row['completion_percentage'],
            "missing_required_fields": missing_fields,
            "is_complete": len(missing_fields) == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing document: {e}")
        raise HTTPException(500, f"Failed to preview document: {str(e)}")


@router.get("/templates/{template_id}/interview-questions")
async def generate_interview_questions(
    template_id: int,
    current_user = Depends(get_current_user)
):
    """
    Generate intelligent interview questions for a template.
    
    Returns:
        List of questions tailored to the template's required fields.
    """
    try:
        pool = await get_db_pool()
        generator = IntelligentDocumentGenerator()
        
        # Get template
        async with pool.acquire() as conn:
            template_row = await conn.fetchrow(f"""
                SELECT id, name, fields_metadata
                FROM {settings.DATABASE_CUSTOMER_SCHEMA}.certification_templates
                WHERE id = $1 AND is_active = true
            """, template_id)
            
            if not template_row:
                raise HTTPException(404, "Template not found")
        
        # Generate questions using AI
        questions = generator.generate_interview_questions(
            fields_metadata=template_row['fields_metadata'],
            template_name=template_row['name']
        )
        
        return {
            "template_id": template_id,
            "template_name": template_row['name'],
            "questions": questions,
            "total_questions": len(questions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating interview questions: {e}")
        raise HTTPException(500, f"Failed to generate questions: {str(e)}")
