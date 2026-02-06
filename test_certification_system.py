"""
Test Certification Template System
===================================
Comprehensive tests for the new certification management features:
- Customer CRUD operations
- Template management
- Intelligent document generation

Run with: python test_certification_system.py
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8400/api"
AUTH_URL = "http://localhost:8401"

# Test credentials (adjust based on your setup)
TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


def get_auth_token():
    """Authenticate and get JWT token."""
    response = requests.post(
        f"{AUTH_URL}/auth/login",
        json=TEST_USER
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Authentication failed: {response.text}")


def test_customer_crud(token):
    """Test customer CRUD operations."""
    print("\n=== Testing Customer CRUD ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create customer
    print("\n1. Creating test customer...")
    customer_data = {
        "name": "Test Corporation Inc.",
        "email": "contact@testcorp.com",
        "phone": "+1-555-0123",
        "address": "123 Test Street, Test City, TC 12345",
        "business_area": "Software Development",
        "notes": "Test customer for certification system"
    }
    
    response = requests.post(
        f"{BASE_URL}/customers",
        headers=headers,
        json=customer_data
    )
    
    if response.status_code == 201:
        customer = response.json()
        print(f"✅ Customer created: ID={customer['id']}, Name={customer['name']}")
        customer_id = customer['id']
    else:
        print(f"❌ Failed to create customer: {response.text}")
        return None
    
    # 2. Get customer
    print(f"\n2. Retrieving customer {customer_id}...")
    response = requests.get(
        f"{BASE_URL}/customers/{customer_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        customer = response.json()
        print(f"✅ Customer retrieved: {customer['name']}")
    else:
        print(f"❌ Failed to retrieve customer: {response.text}")
    
    # 3. List all customers
    print("\n3. Listing all customers...")
    response = requests.get(
        f"{BASE_URL}/customers",
        headers=headers
    )
    
    if response.status_code == 200:
        customers = response.json()
        print(f"✅ Found {len(customers)} customers")
    else:
        print(f"❌ Failed to list customers: {response.text}")
    
    # 4. Update customer
    print(f"\n4. Updating customer {customer_id}...")
    update_data = {
        "business_area": "Financial Technology",
        "notes": "Updated business area to FinTech"
    }
    
    response = requests.put(
        f"{BASE_URL}/customers/{customer_id}",
        headers=headers,
        json=update_data
    )
    
    if response.status_code == 200:
        updated = response.json()
        print(f"✅ Customer updated: Business Area={updated['business_area']}")
    else:
        print(f"❌ Failed to update customer: {response.text}")
    
    return customer_id


def test_certification_listing(token):
    """Test certification listing."""
    print("\n=== Testing Certification Listing ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/certifications",
        headers=headers
    )
    
    if response.status_code == 200:
        certifications = response.json()
        print(f"✅ Found {len(certifications)} available certifications:")
        for cert in certifications:
            print(f"   - {cert['name']} ({cert['code']})")
        return certifications
    else:
        print(f"❌ Failed to list certifications: {response.text}")
        return []


def test_template_listing(token):
    """Test template listing."""
    print("\n=== Testing Template Listing ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/templates",
        headers=headers
    )
    
    if response.status_code == 200:
        templates = response.json()
        print(f"✅ Found {len(templates)} templates")
        if templates:
            for template in templates:
                print(f"   - {template['name']} (Type: {template['document_type']})")
        else:
            print("   ℹ️  No templates uploaded yet")
        return templates
    else:
        print(f"❌ Failed to list templates: {response.text}")
        return []


def test_interview_questions(token, template_id):
    """Test interview question generation."""
    print(f"\n=== Testing Interview Question Generation (Template {template_id}) ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/templates/{template_id}/interview-questions",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Generated {result['total_questions']} questions:")
        for i, question in enumerate(result['questions'][:5], 1):  # Show first 5
            print(f"   {i}. {question['question']}")
            if 'field_name' in question:
                print(f"      → For field: {question['field_name']}")
        return result['questions']
    else:
        print(f"❌ Failed to generate questions: {response.text}")
        return []


def test_document_generation_from_text(token, customer_id, template_id):
    """Test document generation from free text."""
    print(f"\n=== Testing Document Generation from Free Text ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, create a customer certification record
    print("\n1. Creating customer certification record...")
    cert_data = {
        "customer_id": customer_id,
        "certification_id": 1,  # ISO 27001
        "status": "in_progress",
        "progress_percentage": 0.0
    }
    
    # Note: You'll need to add this endpoint or create it manually
    # For now, let's assume certification_id = 1 exists
    
    # Sample customer description
    description = """
    Our company, Test Corporation Inc., is a software development firm specializing 
    in cloud-based financial applications. We have 50 employees and operate from 
    our headquarters in Test City. Our main operations involve:
    
    - Developing secure payment processing systems
    - Cloud infrastructure management using AWS
    - Regular security audits and penetration testing
    - 24/7 system monitoring and incident response
    
    For patch management, we currently use automated tools to deploy security patches
    on a monthly schedule. Critical patches are deployed within 48 hours. We maintain
    detailed logs of all patch activities and have a rollback procedure in case of issues.
    
    Our approval process involves review by the IT Security Manager (John Smith) and 
    final approval by the CTO (Jane Doe). All patches are tested in our staging environment
    before production deployment.
    """
    
    print("\n2. Generating document from customer description...")
    gen_data = {
        "template_id": template_id,
        "customer_id": customer_id,
        "customer_certification_id": 1,  # Assuming ID 1
        "description": description
    }
    
    response = requests.post(
        f"{BASE_URL}/templates/documents/generate-from-text",
        headers=headers,
        json=gen_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Document generated successfully!")
        print(f"   - Document ID: {result['document_id']}")
        print(f"   - Completion: {result['completion_percentage']}%")
        print(f"   - Filled Fields: {result['filled_fields']}/{result['total_fields']}")
        print(f"   - Status: {result['status']}")
        return result['document_id']
    else:
        print(f"❌ Failed to generate document: {response.text}")
        return None


def test_document_preview(token, document_id):
    """Test document preview."""
    print(f"\n=== Testing Document Preview (Document {document_id}) ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/templates/documents/{document_id}/preview",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Document preview generated!")
        print(f"   - Template: {result['template_name']}")
        print(f"   - Completion: {result['completion_percentage']}%")
        print(f"   - Complete: {'Yes' if result['is_complete'] else 'No'}")
        
        if result['missing_required_fields']:
            print(f"   - Missing required fields: {len(result['missing_required_fields'])}")
            for field in result['missing_required_fields']:
                print(f"      • {field['label']}")
        
        # Show first 500 characters of filled document
        if 'filled_document' in result:
            preview_text = result['filled_document'][:500]
            print(f"\n   Preview (first 500 chars):")
            print(f"   {preview_text}...")
        
        return result
    else:
        print(f"❌ Failed to preview document: {response.text}")
        return None


def test_document_refinement(token, document_id):
    """Test document refinement with feedback."""
    print(f"\n=== Testing Document Refinement (Document {document_id}) ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    feedback = """
    Please update the following:
    1. Change the patch deployment schedule to bi-weekly instead of monthly
    2. Add that we use Microsoft SCCM for patch management
    3. Update the approval timeframe for critical patches to 24 hours
    """
    
    response = requests.put(
        f"{BASE_URL}/templates/documents/{document_id}/refine",
        headers=headers,
        json={"feedback": feedback}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Document refined successfully!")
        print(f"   - New Version: {result['version']}")
        print(f"   - Completion: {result['completion_percentage']}%")
        print(f"   - Changes Applied: {result['changes_applied']}")
        return result
    else:
        print(f"❌ Failed to refine document: {response.text}")
        return None


def main():
    """Run all tests."""
    print("=" * 70)
    print("DNA CERTIFICATION SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    try:
        # Get authentication token
        print("\n🔐 Authenticating...")
        token = get_auth_token()
        print("✅ Authentication successful")
        
        # Test customer CRUD
        customer_id = test_customer_crud(token)
        
        if not customer_id:
            print("\n⚠️  Cannot proceed without customer. Exiting.")
            return
        
        # Test certification listing
        certifications = test_certification_listing(token)
        
        # Test template listing
        templates = test_template_listing(token)
        
        # If templates exist, test document generation
        if templates:
            template_id = templates[0]['id']
            
            # Test interview questions
            questions = test_interview_questions(token, template_id)
            
            # Test document generation
            document_id = test_document_generation_from_text(
                token, customer_id, template_id
            )
            
            if document_id:
                # Test document preview
                preview = test_document_preview(token, document_id)
                
                # Test document refinement
                refinement = test_document_refinement(token, document_id)
                
                # Preview again after refinement
                if refinement:
                    print("\n📄 Previewing refined document...")
                    test_document_preview(token, document_id)
        else:
            print("\n⚠️  No templates available for document generation tests")
            print("   To test document generation:")
            print("   1. Upload a Word document template via the API")
            print("   2. Run this test suite again")
        
        print("\n" + "=" * 70)
        print("✅ TEST SUITE COMPLETED")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
