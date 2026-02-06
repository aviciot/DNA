"""
DNA Backend - Intelligent Document Generator
=============================================
Uses LLM to intelligently fill templates based on customer information
and various input sources (interview, free text, email, etc.)
"""

import anthropic
import json
import logging
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)


class IntelligentDocumentGenerator:
    """Generate complete documents using Claude based on templates and user input."""
    
    def __init__(self):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )
        self.model = "claude-sonnet-4-20250514"
    
    def generate_from_interview(
        self,
        template_structure: Dict,
        fields_metadata: List[Dict],
        customer_info: Dict,
        interview_responses: Dict
    ) -> Dict[str, str]:
        """
        Generate document content from structured interview responses.
        
        Args:
            template_structure: Parsed template with {{tags}}
            fields_metadata: Field definitions
            customer_info: Customer profile data
            interview_responses: Q&A from customer interview
            
        Returns:
            Dict of field_name -> generated_content
        """
        prompt = f"""You are an ISO certification document specialist helping to complete a certification document.

CUSTOMER INFORMATION:
Company Name: {customer_info.get('name', 'N/A')}
Business Area: {customer_info.get('business_area', 'N/A')}
Email: {customer_info.get('email', 'N/A')}
Phone: {customer_info.get('phone', 'N/A')}
Address: {customer_info.get('address', 'N/A')}

INTERVIEW RESPONSES:
{json.dumps(interview_responses, indent=2)}

DOCUMENT TEMPLATE FIELDS TO FILL:
{json.dumps(fields_metadata, indent=2)}

Your task:
1. Generate appropriate content for EACH field based on customer info and interview responses
2. Use professional, formal language appropriate for ISO certification documents
3. Be specific and detailed - avoid generic placeholder text
4. Ensure consistency across all fields
5. If information is missing, generate reasonable defaults based on context

Return JSON in this EXACT format:
{{
  "field_name_1": "generated content for field 1",
  "field_name_2": "generated content for field 2",
  ...
}}

Generate content for ALL {len(fields_metadata)} fields."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            filled_data = json.loads(response_text)
            logger.info(f"Generated content for {len(filled_data)} fields")
            return filled_data
            
        except Exception as e:
            logger.error(f"Error generating from interview: {e}")
            raise
    
    def generate_from_free_text(
        self,
        template_structure: Dict,
        fields_metadata: List[Dict],
        customer_info: Dict,
        free_text_input: str
    ) -> Dict[str, str]:
        """
        Generate document content from free-form text description.
        
        Args:
            template_structure: Parsed template with {{tags}}
            fields_metadata: Field definitions
            customer_info: Customer profile data
            free_text_input: Free-form description from customer
            
        Returns:
            Dict of field_name -> generated_content
        """
        prompt = f"""You are an ISO certification document specialist helping to complete a certification document.

CUSTOMER INFORMATION:
Company Name: {customer_info.get('name', 'N/A')}
Business Area: {customer_info.get('business_area', 'N/A')}
Email: {customer_info.get('email', 'N/A')}

CUSTOMER'S DESCRIPTION:
{free_text_input}

DOCUMENT TEMPLATE FIELDS TO FILL:
{json.dumps(fields_metadata, indent=2)}

Your task:
1. Extract relevant information from the customer's description
2. Generate appropriate content for EACH field
3. Use professional, formal language appropriate for ISO certification documents
4. Be specific and detailed based on the customer's context
5. Fill ALL fields - making intelligent inferences where needed

Return JSON with filled content for all {len(fields_metadata)} fields:
{{
  "field_name_1": "generated content",
  ...
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            filled_data = json.loads(response_text)
            logger.info(f"Generated content from free text for {len(filled_data)} fields")
            return filled_data
            
        except Exception as e:
            logger.error(f"Error generating from free text: {e}")
            raise
    
    def refine_document(
        self,
        template_structure: Dict,
        current_filled_data: Dict[str, str],
        fields_metadata: List[Dict],
        user_feedback: str
    ) -> Dict[str, str]:
        """
        Refine generated content based on user feedback.
        
        Args:
            template_structure: Parsed template
            current_filled_data: Currently filled field values
            fields_metadata: Field definitions
            user_feedback: User's feedback/correction requests
            
        Returns:
            Updated Dict of field_name -> refined_content
        """
        prompt = f"""You are refining an ISO certification document based on user feedback.

CURRENT DOCUMENT CONTENT:
{json.dumps(current_filled_data, indent=2)}

FIELD DEFINITIONS:
{json.dumps(fields_metadata, indent=2)}

USER FEEDBACK:
{user_feedback}

Your task:
1. Review the user's feedback carefully
2. Update ONLY the fields that need changes based on feedback
3. Keep other fields unchanged
4. Maintain professional, formal language
5. Ensure consistency across all fields

Return JSON with ALL fields (updated + unchanged):
{{
  "field_name_1": "content (updated or unchanged)",
  ...
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            refined_data = json.loads(response_text)
            logger.info(f"Refined {len(refined_data)} fields based on feedback")
            return refined_data
            
        except Exception as e:
            logger.error(f"Error refining document: {e}")
            raise
    
    def generate_interview_questions(
        self,
        fields_metadata: List[Dict],
        document_name: str,
        customer_info: Dict
    ) -> List[Dict]:
        """
        Generate intelligent interview questions to gather information for template.
        
        Args:
            fields_metadata: Field definitions from template
            document_name: Name of the document
            customer_info: Customer profile
            
        Returns:
            List of questions with metadata [{question, purpose, related_fields}]
        """
        prompt = f"""You are creating an interview guide to gather information for an ISO certification document.

DOCUMENT: {document_name}
CUSTOMER: {customer_info.get('name', 'N/A')} - {customer_info.get('business_area', 'N/A')}

FIELDS THAT NEED TO BE FILLED:
{json.dumps(fields_metadata, indent=2)}

Your task:
Create a set of clear, conversational interview questions that will gather all necessary information.
- Ask 5-10 strategic questions that cover multiple fields
- Make questions natural and conversational
- Group related fields into single questions where appropriate
- Tailor questions to the customer's business context

Return JSON:
[
  {{
    "question": "Can you describe your current patch management process?",
    "purpose": "Understanding current practices for policy documentation",
    "related_fields": ["security_team_name", "scan_frequency", "responsible_role_title"],
    "question_type": "open_ended"
  }},
  ...
]"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            questions = json.loads(response_text)
            logger.info(f"Generated {len(questions)} interview questions")
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            raise
