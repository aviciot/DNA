"""
DNA Backend - Customer Documents Routes
========================================
Document generation, filling, and management endpoints.
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from models import (
    CustomerDocument, CustomerDocumentCreate, CustomerDocumentUpdate,
    CustomerDocumentDetail
)
from database import get_db_pool
from auth import get_current_user, require_admin
from services.ai_document_filler import AIDocumentFiller
from services.template_parser import calculate_document_completion, generate_filled_document

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate-from-template", response_model=CustomerDocument, status_code=201)
async def generate_document_from_template(
    customer_certification_id: int,
    template_id: int,
    user_provided_fields: Dict[str, Any] = None,
    auto_fill_with_ai: bool = True,
    current_user = Depends(require_admin)
):
    """
    Generate a new customer document from template.
    
    Args:
        customer_certification_id: Customer certification assignment
        template_id: Template to use
        user_provided_fields: Optional user-provided field values (overrides AI)
        auto_fill_with_ai: Whether to use AI to fill remaining fields
        
    Returns:
        Created document with filled fields
    """
    try:
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            # Get customer certification details
            cert_row = await conn.fetchrow("""
                SELECT cc.id, cc.customer_id, cc.certification_id,
                       c.name, c.email, c.phone, c.address, c.business_area, c.notes,
                       cert.code, cert.name as cert_name, cert.description
                FROM public.customer_certifications cc
                JOIN public.customers c ON cc.customer_id = c.id
                JOIN public.certifications cert ON cc.certification_id = cert.id
                WHERE cc.id = $1
            """, customer_certification_id)
            
            if not cert_row:
                raise HTTPException(404, "Customer certification not found")
            
            # Get template
            template_row = await conn.fetchrow("""
                SELECT id, certification_id, name, description, document_type,
                       template_structure, fields_metadata
                FROM public.certification_templates
                WHERE id = $1 AND is_active = true
            """, template_id)
            
            if not template_row:
                raise HTTPException(404, "Template not found")
            
            template = dict(template_row)
            
            # Prepare customer context
            customer_context = {
                'name': cert_row['name'],
                'email': cert_row['email'],
                'phone': cert_row['phone'],
                'address': cert_row['address'],
                'business_area': cert_row['business_area'],
                'notes': cert_row['notes']
            }
            
            document_context = {
                'certification_name': cert_row['cert_name'],
                'document_type': template['document_type'],
                'document_name': template['name']
            }
            
            # Fill with AI if enabled
            filled_data = user_provided_fields or {}
            
            if auto_fill_with_ai:
                logger.info(f"Using AI to fill document: {template['name']}")
                filler = AIDocumentFiller()
                filled_data = filler.fill_entire_document(
                    template=template,
                    customer_context=customer_context,
                    document_context=document_context,
                    user_provided_fields=user_provided_fields
                )
            
            # Calculate completion
            completion = calculate_document_completion(
                filled_data,
                template['fields_metadata']
            )
            
            # Determine status
            status = 'draft' if completion < 100 else 'in_progress'
            
            # Create document
            doc_row = await conn.fetchrow("""
                INSERT INTO public.customer_documents
                (customer_certification_id, template_id, document_name, filled_data,
                 status, completion_percentage, assigned_to, version)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 1)
                RETURNING id, customer_certification_id, template_id, document_name,
                          filled_data, status, completion_percentage, assigned_to,
                          reviewed_by, reviewed_at, notes, version, created_at, updated_at
            """, customer_certification_id, template_id, template['name'],
                filled_data, status, completion, current_user["user_id"])
            
            logger.info(f"Document created with AI: ID={doc_row['id']}, Completion={completion}%")
            return CustomerDocument(**dict(doc_row))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating document from template: {e}")
        raise HTTPException(500, f"Failed to generate document: {str(e)}")


@router.post("/batch-generate-certification", status_code=201)
async def batch_generate_certification_documents(
    customer_certification_id: int,
    template_ids: List[int] = None,
    current_user = Depends(require_admin)
):
    """
    Generate all documents for a certification at once with AI.
    
    Args:
        customer_certification_id: Customer certification assignment
        template_ids: Optional list of template IDs (if None, generates all for certification)
        
    Returns:
        List of generated document IDs and summary
    """
    try:
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            # Get customer certification
            cert_row = await conn.fetchrow("""
                SELECT cc.id, cc.customer_id, cc.certification_id,
                       c.name, c.email, c.phone, c.address, c.business_area, c.notes,
                       cert.code, cert.name as cert_name
                FROM public.customer_certifications cc
                JOIN public.customers c ON cc.customer_id = c.id
                JOIN public.certifications cert ON cc.certification_id = cert.id
                WHERE cc.id = $1
            """, customer_certification_id)
            
            if not cert_row:
                raise HTTPException(404, "Customer certification not found")
            
            # Get templates
            if template_ids:
                templates_rows = await conn.fetch("""
                    SELECT id, certification_id, name, description, document_type,
                           template_structure, fields_metadata
                    FROM public.certification_templates
                    WHERE id = ANY($1) AND is_active = true
                """, template_ids)
            else:
                templates_rows = await conn.fetch("""
                    SELECT id, certification_id, name, description, document_type,
                           template_structure, fields_metadata
                    FROM public.certification_templates
                    WHERE certification_id = $1 AND is_active = true
                """, cert_row['certification_id'])
            
            if not templates_rows:
                raise HTTPException(404, "No templates found")
            
            # Prepare context
            customer_context = {
                'name': cert_row['name'],
                'email': cert_row['email'],
                'phone': cert_row['phone'],
                'address': cert_row['address'],
                'business_area': cert_row['business_area'],
                'notes': cert_row['notes']
            }
            
            filler = AIDocumentFiller()
            generated_docs = []
            
            logger.info(f"Batch generating {len(templates_rows)} documents for {cert_row['name']}")
            
            # Generate each document
            for template in templates_rows:
                template_dict = dict(template)
                
                document_context = {
                    'certification_name': cert_row['cert_name'],
                    'document_type': template_dict['document_type'],
                    'document_name': template_dict['name']
                }
                
                # Fill with AI
                filled_data = filler.fill_entire_document(
                    template=template_dict,
                    customer_context=customer_context,
                    document_context=document_context
                )
                
                # Calculate completion
                completion = calculate_document_completion(
                    filled_data,
                    template_dict['fields_metadata']
                )
                
                # Create document
                doc_row = await conn.fetchrow("""
                    INSERT INTO public.customer_documents
                    (customer_certification_id, template_id, document_name, filled_data,
                     status, completion_percentage, assigned_to, version)
                    VALUES ($1, $2, $3, $4, 'in_progress', $5, $6, 1)
                    RETURNING id, document_name, completion_percentage
                """, customer_certification_id, template_dict['id'], template_dict['name'],
                    filled_data, completion, current_user["user_id"])
                
                generated_docs.append({
                    'id': doc_row['id'],
                    'name': doc_row['document_name'],
                    'completion': doc_row['completion_percentage']
                })
                
                logger.info(f"Generated: {doc_row['document_name']} ({completion}% complete)")
            
            # Update customer certification progress
            total_completion = sum(d['completion'] for d in generated_docs) / len(generated_docs)
            await conn.execute("""
                UPDATE public.customer_certifications
                SET progress_percentage = $1, status = 'in_progress'
                WHERE id = $2
            """, round(total_completion, 2), customer_certification_id)
            
            logger.info(f"✅ Batch generation complete: {len(generated_docs)} documents, {total_completion:.1f}% avg completion")
            
            return {
                'success': True,
                'documents_generated': len(generated_docs),
                'total_completion': round(total_completion, 2),
                'documents': generated_docs
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error batch generating documents: {e}")
        raise HTTPException(500, f"Failed to batch generate: {str(e)}")


@router.get("/{document_id}", response_model=CustomerDocumentDetail)
async def get_document(document_id: int, current_user = Depends(get_current_user)):
    """Get customer document with template details."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    cd.id, cd.customer_certification_id, cd.template_id, cd.document_name,
                    cd.filled_data, cd.status, cd.completion_percentage, cd.assigned_to,
                    cd.reviewed_by, cd.reviewed_at, cd.notes, cd.version,
                    cd.created_at, cd.updated_at,
                    ct.certification_id, ct.name as template_name, ct.description,
                    ct.document_type, ct.template_structure, ct.fields_metadata,
                    ct.original_filename, ct.file_url, ct.version as template_version,
                    ct.is_active, ct.created_by, ct.created_at as template_created_at,
                    ct.updated_at as template_updated_at
                FROM public.customer_documents cd
                JOIN public.certification_templates ct ON cd.template_id = ct.id
                WHERE cd.id = $1
            """, document_id)
            
            if not row:
                raise HTTPException(404, "Document not found")
            
            from models import CertificationTemplate
            
            # Build response with template details
            doc_data = CustomerDocument(**{
                'id': row['id'],
                'customer_certification_id': row['customer_certification_id'],
                'template_id': row['template_id'],
                'document_name': row['document_name'],
                'filled_data': row['filled_data'],
                'status': row['status'],
                'completion_percentage': row['completion_percentage'],
                'assigned_to': row['assigned_to'],
                'reviewed_by': row['reviewed_by'],
                'reviewed_at': row['reviewed_at'],
                'notes': row['notes'],
                'version': row['version'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
            
            template_data = CertificationTemplate(**{
                'id': row['template_id'],
                'certification_id': row['certification_id'],
                'name': row['template_name'],
                'description': row['description'],
                'document_type': row['document_type'],
                'template_structure': row['template_structure'],
                'fields_metadata': row['fields_metadata'],
                'original_filename': row['original_filename'],
                'file_url': row['file_url'],
                'version': row['template_version'],
                'is_active': row['is_active'],
                'created_by': row['created_by'],
                'created_at': row['template_created_at'],
                'updated_at': row['template_updated_at']
            })
            
            return CustomerDocumentDetail(**doc_data.dict(), template=template_data)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(500, "Failed to retrieve document")


@router.put("/{document_id}", response_model=CustomerDocument)
async def update_document(
    document_id: int,
    update: CustomerDocumentUpdate,
    current_user = Depends(get_current_user)
):
    """Update document fields or status."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Get current document and template
            doc_row = await conn.fetchrow("""
                SELECT cd.filled_data, ct.fields_metadata
                FROM public.customer_documents cd
                JOIN public.certification_templates ct ON cd.template_id = ct.id
                WHERE cd.id = $1
            """, document_id)
            
            if not doc_row:
                raise HTTPException(404, "Document not found")
            
            # Build update
            updates = []
            params = []
            param_count = 1
            
            if update.filled_data is not None:
                # Recalculate completion
                completion = calculate_document_completion(
                    update.filled_data,
                    doc_row['fields_metadata']
                )
                updates.append(f"filled_data = ${param_count}")
                params.append(update.filled_data)
                param_count += 1
                updates.append(f"completion_percentage = ${param_count}")
                params.append(completion)
                param_count += 1
            
            if update.status is not None:
                updates.append(f"status = ${param_count}")
                params.append(update.status)
                param_count += 1
            
            if update.assigned_to is not None:
                updates.append(f"assigned_to = ${param_count}")
                params.append(update.assigned_to)
                param_count += 1
            
            if update.reviewed_by is not None:
                updates.append(f"reviewed_by = ${param_count}")
                params.append(update.reviewed_by)
                param_count += 1
                updates.append(f"reviewed_at = NOW()")
            
            if update.notes is not None:
                updates.append(f"notes = ${param_count}")
                params.append(update.notes)
                param_count += 1
            
            if not updates:
                return await get_document(document_id, current_user)
            
            params.append(document_id)
            query = f"""
                UPDATE public.customer_documents
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, customer_certification_id, template_id, document_name,
                          filled_data, status, completion_percentage, assigned_to,
                          reviewed_by, reviewed_at, notes, version, created_at, updated_at
            """
            
            row = await conn.fetchrow(query, *params)
            return CustomerDocument(**dict(row))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        raise HTTPException(500, "Failed to update document")


@router.get("/{document_id}/preview")
async def preview_filled_document(document_id: int, current_user = Depends(get_current_user)):
    """Generate preview of filled document."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT cd.filled_data, ct.template_structure
                FROM public.customer_documents cd
                JOIN public.certification_templates ct ON cd.template_id = ct.id
                WHERE cd.id = $1
            """, document_id)
            
            if not row:
                raise HTTPException(404, "Document not found")
            
            # Generate filled document
            filled_document = generate_filled_document(
                row['template_structure'],
                row['filled_data']
            )
            
            return {
                'success': True,
                'document_id': document_id,
                'preview': filled_document
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing document: {e}")
        raise HTTPException(500, "Failed to generate preview")


@router.post("/{document_id}/refine-field")
async def refine_field_with_ai(
    document_id: int,
    field_name: str,
    feedback: str,
    current_user = Depends(get_current_user)
):
    """Refine a specific field using AI based on user feedback."""
    try:
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            # Get document, template, and customer info
            row = await conn.fetchrow("""
                SELECT 
                    cd.filled_data, ct.fields_metadata, ct.name as doc_name,
                    c.name, c.business_area, cert.name as cert_name
                FROM public.customer_documents cd
                JOIN public.certification_templates ct ON cd.template_id = ct.id
                JOIN public.customer_certifications cc ON cd.customer_certification_id = cc.id
                JOIN public.customers c ON cc.customer_id = c.id
                JOIN public.certifications cert ON cc.certification_id = cert.id
                WHERE cd.id = $1
            """, document_id)
            
            if not row:
                raise HTTPException(404, "Document not found")
            
            # Find field metadata
            field_meta = next(
                (f for f in row['fields_metadata'] if f['name'] == field_name),
                None
            )
            if not field_meta:
                raise HTTPException(404, f"Field '{field_name}' not found")
            
            current_content = row['filled_data'].get(field_name, '')
            
            # Refine with AI
            filler = AIDocumentFiller()
            refined_content = filler.refine_field_with_feedback(
                field_name=field_name,
                current_content=current_content,
                feedback=feedback,
                field_metadata=field_meta,
                customer_context={'name': row['name'], 'business_area': row['business_area']},
                document_context={'document_name': row['doc_name'], 'certification_name': row['cert_name']}
            )
            
            # Update document
            filled_data = dict(row['filled_data'])
            filled_data[field_name] = refined_content
            
            # Recalculate completion
            completion = calculate_document_completion(filled_data, row['fields_metadata'])
            
            await conn.execute("""
                UPDATE public.customer_documents
                SET filled_data = $1, completion_percentage = $2
                WHERE id = $3
            """, filled_data, completion, document_id)
            
            return {
                'success': True,
                'field_name': field_name,
                'refined_content': refined_content,
                'completion_percentage': completion
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refining field: {e}")
        raise HTTPException(500, "Failed to refine field")
