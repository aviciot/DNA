"""
DNA Phase 2 E2E Test - Template-ISO Association
================================================
Tests the complete workflow for associating templates with ISO standards.

Flow:
1. Login and get token
2. Get list of ISO standards
3. Get list of templates
4. Associate template with ISO standard(s)
5. Verify association by querying both directions
6. Update associations
7. Verify updates
"""

import requests
import time
import sys
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8400"
AUTH_BASE = "http://localhost:8401"
CREDENTIALS = {
    "email": "admin@dna.local",
    "password": "admin123"
}

def log(message, level="INFO"):
    """Print log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{timestamp}] [{level}] {message}")
    except UnicodeEncodeError:
        safe_message = message.encode('ascii', errors='replace').decode('ascii')
        print(f"[{timestamp}] [{level}] {safe_message}")


def test_login():
    """Test login and return token."""
    log("=== Step 1: Login ===")

    response = requests.post(
        f"{AUTH_BASE}/api/v1/auth/login",
        json=CREDENTIALS
    )

    if response.status_code == 200:
        token = response.json()["access_token"]
        log(f"OK Login successful")
        return token
    else:
        log(f"FAIL Login failed: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_get_iso_standards(token):
    """Get list of ISO standards."""
    log("=== Step 2: Get ISO Standards ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/api/v1/iso-standards",
        headers=headers
    )

    if response.status_code == 200:
        iso_standards = response.json()
        log(f"OK Found {len(iso_standards)} ISO standards")

        if len(iso_standards) > 0:
            for iso in iso_standards[:3]:  # Show first 3
                log(f"  - {iso['code']}: {iso['name']}")
            return iso_standards
        else:
            log("FAIL No ISO standards found in database", "ERROR")
            sys.exit(1)
    else:
        log(f"FAIL Failed to get ISO standards: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_get_templates(token):
    """Get list of templates."""
    log("=== Step 3: Get Templates ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/api/v1/template-analysis/templates",
        headers=headers
    )

    if response.status_code == 200:
        templates = response.json()
        log(f"OK Found {len(templates)} templates")

        if len(templates) > 0:
            for template in templates[:3]:  # Show first 3
                log(f"  - {template['name']} (Status: {template['status']})")
            return templates
        else:
            log("FAIL No templates found in database", "ERROR")
            log("     Please create templates first using test_template_analysis_e2e.py", "ERROR")
            sys.exit(1)
    else:
        log(f"FAIL Failed to get templates: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_associate_template_with_iso(token, template_id, iso_ids):
    """Associate template with ISO standards."""
    log(f"=== Step 4: Associate Template with {len(iso_ids)} ISO Standard(s) ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{API_BASE}/api/v1/template-analysis/templates/{template_id}/iso-standards",
        headers=headers,
        json={"iso_standard_ids": iso_ids}
    )

    if response.status_code == 200:
        result = response.json()
        log(f"OK Association successful")
        log(f"  Template ID: {result['template_id']}")
        log(f"  Associated ISO Standards:")
        for iso in result['iso_standards']:
            log(f"    - {iso['code']}: {iso['name']}")
        return result
    else:
        log(f"FAIL Association failed: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_get_template_iso_standards(token, template_id):
    """Get ISO standards for a template."""
    log(f"=== Step 5a: Get ISO Standards for Template ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/api/v1/template-analysis/templates/{template_id}/iso-standards",
        headers=headers
    )

    if response.status_code == 200:
        result = response.json()
        log(f"OK Template has {result['count']} ISO standard(s)")
        for iso in result['iso_standards']:
            log(f"  - {iso['code']}: {iso['name']}")
        return result
    else:
        log(f"FAIL Failed to get template ISO standards: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_get_iso_templates(token, iso_id, iso_code):
    """Get templates for an ISO standard."""
    log(f"=== Step 5b: Get Templates for ISO {iso_code} ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/api/v1/template-analysis/iso-standards/{iso_id}/templates",
        headers=headers
    )

    if response.status_code == 200:
        result = response.json()
        log(f"OK ISO standard has {result['count']} template(s)")
        for template in result['templates']:
            log(f"  - {template['name']} (Status: {template['status']})")
        return result
    else:
        log(f"FAIL Failed to get ISO templates: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_update_template_iso_standards(token, template_id, iso_ids):
    """Update ISO standards for a template."""
    log(f"=== Step 6: Update Template ISO Associations ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(
        f"{API_BASE}/api/v1/template-analysis/templates/{template_id}/iso-standards",
        headers=headers,
        json={"iso_standard_ids": iso_ids}
    )

    if response.status_code == 200:
        result = response.json()
        log(f"OK Update successful")
        log(f"  Template ID: {result['template_id']}")
        log(f"  Updated ISO Standards:")
        for iso in result['iso_standards']:
            log(f"    - {iso['code']}: {iso['name']}")
        return result
    else:
        log(f"FAIL Update failed: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def test_verify_bidirectional(token, template_id, iso_id, expected_count):
    """Verify association works in both directions."""
    log(f"=== Step 7: Verify Bidirectional Association ===")

    # Check template → ISO
    result1 = test_get_template_iso_standards(token, template_id)

    # Check ISO → template
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE}/api/v1/template-analysis/iso-standards/{iso_id}/templates",
        headers=headers
    )

    if response.status_code == 200:
        result2 = response.json()

        # Verify consistency
        if result1['count'] == expected_count:
            log(f"OK Template has correct number of ISO standards ({expected_count})")
        else:
            log(f"FAIL Template ISO count mismatch: expected {expected_count}, got {result1['count']}", "ERROR")
            sys.exit(1)

        # Check if template is in ISO's list
        template_ids = [t['id'] for t in result2['templates']]
        if template_id in template_ids:
            log(f"OK Template found in ISO's template list")
        else:
            log(f"FAIL Template not found in ISO's template list", "ERROR")
            sys.exit(1)

        log("OK Bidirectional association verified successfully")
    else:
        log(f"FAIL Failed to verify: {response.status_code} - {response.text}", "ERROR")
        sys.exit(1)


def main():
    """Run complete Phase 2 E2E test."""
    start_time = time.time()

    log("=" * 70)
    log("DNA Phase 2 E2E Test - Template-ISO Association")
    log("=" * 70)

    try:
        # Step 1: Login
        token = test_login()

        # Step 2: Get ISO standards
        iso_standards = test_get_iso_standards(token)

        # Step 3: Get templates
        templates = test_get_templates(token)

        # Use first active template
        active_templates = [t for t in templates if t['status'] == 'active']
        if not active_templates:
            log("FAIL No active templates found. Using first template anyway.", "WARN")
            template = templates[0]
        else:
            template = active_templates[0]

        template_id = template['id']
        log(f"Using template: {template['name']} (ID: {template_id})")

        # Use first two ISO standards
        iso_1 = iso_standards[0]
        iso_2 = iso_standards[1] if len(iso_standards) > 1 else iso_standards[0]

        # Step 4: Associate template with ISO standards
        test_associate_template_with_iso(
            token,
            template_id,
            [iso_1['id'], iso_2['id']]
        )

        # Step 5: Verify associations (both directions)
        test_get_template_iso_standards(token, template_id)
        test_get_iso_templates(token, iso_1['id'], iso_1['code'])

        # Step 6: Update to single ISO
        log(f"Now updating to only one ISO standard: {iso_1['code']}")
        test_update_template_iso_standards(
            token,
            template_id,
            [iso_1['id']]
        )

        # Step 7: Verify update worked
        test_verify_bidirectional(token, template_id, iso_1['id'], expected_count=1)

        # Success!
        duration = time.time() - start_time
        log("=" * 70)
        log(f"SUCCESS All Phase 2 tests passed! Duration: {duration:.2f}s", "SUCCESS")
        log("=" * 70)

        log("\nPhase 2 Implementation Status:")
        log("  ✅ POST /templates/{id}/iso-standards - Associate template with ISO")
        log("  ✅ GET /templates/{id}/iso-standards - Get template's ISO standards")
        log("  ✅ PUT /templates/{id}/iso-standards - Update template's ISO standards")
        log("  ✅ GET /iso-standards/{id}/templates - Get ISO's templates")
        log("  ✅ Bidirectional association verified")
        log("\nNext: Phase 3 - Customer Assignment")

    except KeyboardInterrupt:
        log("\nTest interrupted by user", "WARN")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
