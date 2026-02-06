"""
DNA Backend - AI Document Filler Service
=========================================
Uses LLM to intelligently fill certification templates based on customer context.
"""

import anthropic
import json
import logging
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)


class AIDocumentFiller:
    """Intelligently fill document templates using Claude with context."""
    
    def __init__(self):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )
        self.model = "claude-sonnet-4-20250514"
    
    def generate_field_content(
        self,
        field_metadata: Dict,
        customer_context: Dict,
        document_context: Dict,
        existing_fields: Dict = None
    ) -> str:
        """
        Generate intelligent content for a single field.
        
        Args:
            field_metadata: Field definition (name, type, description, etc.)
            customer_context: Customer information (company, business, size, etc.)
            document_context: Document info (certification, type, goals)
            existing_fields: Previously filled fields for context
            
        Returns:
            Generated content for the field
        """
        try:
            # Build context for Claude
            prompt = f"""You are an ISO certification expert helping to complete a certification document.

CUSTOMER INFORMATION:
- Company Name: {customer_context.get('name', 'N/A')}
- Business Area: {customer_context.get('business_area', 'N/A')}
- Company Size: {customer_context.get('company_size', 'N/A')}
- Industry: {customer_context.get('industry', 'N/A')}
- Additional Context: {customer_context.get('notes', 'N/A')}

DOCUMENT INFORMATION:
- Certification: {document_context.get('certification_name', 'N/A')}
- Document Type: {document_context.get('document_type', 'N/A')}
- Document Name: {document_context.get('document_name', 'N/A')}

FIELD TO FILL:
- Field Name: {field_metadata.get('name')}
- Field Type: {field_metadata.get('type')}
- Description: {field_metadata.get('description')}
- Section: {field_metadata.get('section', 'N/A')}

{f"PREVIOUSLY FILLED FIELDS (for context):\\n{json.dumps(existing_fields, indent=2)}" if existing_fields else ""}

TASK:
Generate appropriate, professional, and contextually accurate content for this field.
- Keep it concise and business-appropriate
- Match the tone of an ISO certification document
- Use the customer's actual information where relevant
- For dates, use ISO format (YYYY-MM-DD)
- For policies/procedures, write professional, clear guidance

Respond with ONLY the content to fill in this field, nothing else."""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,  # Balanced creativity
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = message.content[0].text.strip()
            
            # Clean up any markdown formatting
            content = content.replace('**', '').replace('*', '')
            
            logger.info(f"Generated content for field '{field_metadata.get('name')}': {len(content)} chars")
            return content
            
        except Exception as e:
            logger.error(f"Error generating field content: {e}")
            # Return sensible default based on field type
            return self._get_default_value(field_metadata, customer_context)
    
    def fill_entire_document(
        self,
        template: Dict,
        customer_context: Dict,
        document_context: Dict,
        user_provided_fields: Dict = None
    ) -> Dict:
        """
        Fill an entire document template intelligently.
        
        Args:
            template: Template structure with fields_metadata
            customer_context: Customer information
            document_context: Document information
            user_provided_fields: Fields user explicitly provided (overrides AI)
            
        Returns:
            Dict of field_name -> generated_content
        """
        try:
            filled_data = {}
            user_provided_fields = user_provided_fields or {}
            
            # Get all fields from template
            fields_metadata = template.get('fields_metadata', [])
            
            logger.info(f"Filling document with {len(fields_metadata)} fields")
            
            # Process fields in order, building context as we go
            for field in fields_metadata:
                field_name = field.get('name')
                
                # Skip if user already provided this field
                if field_name in user_provided_fields:
                    filled_data[field_name] = user_provided_fields[field_name]
                    logger.info(f"Using user-provided value for '{field_name}'")
                    continue
                
                # Check for auto-fill from customer profile
                auto_value = self._auto_fill_from_customer(field, customer_context)
                if auto_value:
                    filled_data[field_name] = auto_value
                    logger.info(f"Auto-filled '{field_name}' from customer profile")
                    continue
                
                # Generate with AI
                generated_content = self.generate_field_content(
                    field_metadata=field,
                    customer_context=customer_context,
                    document_context=document_context,
                    existing_fields=filled_data  # Pass context from already-filled fields
                )
                
                filled_data[field_name] = generated_content
            
            logger.info(f"Document filling complete: {len(filled_data)} fields filled")
            return filled_data
            
        except Exception as e:
            logger.error(f"Error filling entire document: {e}")
            raise
    
    def _auto_fill_from_customer(self, field: Dict, customer_context: Dict) -> Optional[str]:
        """Try to auto-fill field from customer profile."""
        field_name = field.get('name', '').lower()
        
        # Direct mappings
        if 'company_name' in field_name or 'organization_name' in field_name:
            return customer_context.get('name')
        
        if 'email' in field_name and 'secondary' not in field_name:
            return customer_context.get('email')
        
        if 'secondary_email' in field_name:
            return customer_context.get('secondary_email')
        
        if 'phone' in field_name:
            return customer_context.get('phone')
        
        if 'address' in field_name:
            return customer_context.get('address')
        
        if 'business_area' in field_name or 'industry' in field_name:
            return customer_context.get('business_area')
        
        return None
    
    def _get_default_value(self, field: Dict, customer_context: Dict) -> str:
        """Get sensible default value based on field type."""
        field_type = field.get('type', 'text')
        field_name = field.get('name', '')
        
        if field_type == 'date':
            from datetime import datetime
            return datetime.now().strftime('%Y-%m-%d')
        
        if field_type == 'select' and field.get('options'):
            return field['options'][0]  # First option
        
        if 'company' in field_name.lower():
            return customer_context.get('name', 'Company Name')
        
        return '[To be determined]'
    
    def refine_field_with_feedback(
        self,
        field_name: str,
        current_content: str,
        feedback: str,
        field_metadata: Dict,
        customer_context: Dict,
        document_context: Dict
    ) -> str:
        """
        Refine a field's content based on user feedback.
        
        Args:
            field_name: Name of the field
            current_content: Current generated content
            feedback: User's feedback/correction request
            field_metadata: Field definition
            customer_context: Customer info
            document_context: Document info
            
        Returns:
            Refined content
        """
        try:
            prompt = f"""You are refining content for a certification document based on user feedback.

CUSTOMER: {customer_context.get('name', 'N/A')}
DOCUMENT: {document_context.get('document_name', 'N/A')}
FIELD: {field_name} - {field_metadata.get('description', 'N/A')}

CURRENT CONTENT:
{current_content}

USER FEEDBACK:
{feedback}

TASK:
Revise the content based on the user's feedback while maintaining professional ISO certification standards.
Respond with ONLY the revised content, nothing else."""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            refined_content = message.content[0].text.strip()
            refined_content = refined_content.replace('**', '').replace('*', '')
            
            logger.info(f"Refined field '{field_name}' based on feedback")
            return refined_content
            
        except Exception as e:
            logger.error(f"Error refining field content: {e}")
            return current_content  # Return unchanged if error


def generate_complete_certification_suite(
    customer_context: Dict,
    certification_id: int,
    templates: List[Dict],
    anthropic_api_key: str
) -> Dict[int, Dict]:
    """
    Generate all documents for a complete certification (e.g., all 21 ISO 27001 documents).
    
    Args:
        customer_context: Customer information
        certification_id: ID of certification being pursued
        templates: List of all template structures for this certification
        anthropic_api_key: API key
        
    Returns:
        Dict mapping template_id -> filled_data
    """
    filler = AIDocumentFiller()
    results = {}
    
    logger.info(f"Generating complete certification suite: {len(templates)} documents")
    
    for template in templates:
        template_id = template.get('id')
        document_context = {
            'certification_name': template.get('certification_name', 'ISO Certification'),
            'document_type': template.get('document_type', 'document'),
            'document_name': template.get('name', 'Document')
        }
        
        filled_data = filler.fill_entire_document(
            template=template,
            customer_context=customer_context,
            document_context=document_context
        )
        
        results[template_id] = filled_data
        logger.info(f"Completed document: {document_context['document_name']}")
    
    logger.info("✅ Complete certification suite generated!")
    return results
