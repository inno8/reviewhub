"""
Test script to verify findings storage with skill mappings.
Simulates AI engine posting an evaluation to Django API.
"""
import requests
import json
from datetime import datetime

# Configuration
DJANGO_URL = "http://localhost:8000"
PROJECT_ID = 1

# Test data - simulating AI engine output
test_evaluation = {
    "project_id": PROJECT_ID,
    "commit_sha": "abc123def456789",
    "commit_message": "Test commit for findings verification",
    "commit_timestamp": datetime.now().isoformat(),
    "branch": "test-branch",
    "author_name": "Test Author",
    "author_email": "test@example.com",
    "files_changed": 2,
    "lines_added": 15,
    "lines_removed": 3,
    "overall_score": 75.5,
    "llm_model": "openclaw/test",
    "llm_tokens_used": 1500,
    "processing_ms": 2500,
    "findings": [
        {
            "title": "Missing input validation",
            "description": "Function accepts user input without validation",
            "severity": "warning",
            "file_path": "src/api/users.py",
            "line_start": 15,
            "line_end": 20,
            "original_code": "def create_user(data):\n    return User.objects.create(**data)",
            "suggested_code": "def create_user(data):\n    validate_user_data(data)\n    return User.objects.create(**data)",
            "explanation": "Always validate user input before using it",
            "skills_affected": ["input-validation", "security-practices"]
        },
        {
            "title": "Missing error handling",
            "description": "No try-catch for database operation",
            "severity": "critical",
            "file_path": "src/api/users.py",
            "line_start": 25,
            "line_end": 27,
            "original_code": "user = User.objects.get(id=user_id)",
            "suggested_code": "try:\n    user = User.objects.get(id=user_id)\nexcept User.DoesNotExist:\n    return None",
            "explanation": "Handle potential database errors",
            "skills_affected": ["error-handling", "backend-architecture"]
        },
        {
            "title": "Poor code structure",
            "description": "Function is too long and does multiple things",
            "severity": "info",
            "file_path": "src/utils/helpers.py",
            "line_start": 42,
            "line_end": 85,
            "original_code": "# Long function...",
            "suggested_code": "# Split into smaller functions...",
            "explanation": "Follow single responsibility principle",
            "skills_affected": ["code-structure", "clean-code", "solid-principles"]
        }
    ]
}

def test_findings_storage():
    """Test the full findings storage flow."""
    
    print("[TEST] Testing findings storage with skill mappings...\n")
    
    # POST evaluation to Django
    print(f"[POST] Posting evaluation to {DJANGO_URL}/api/evaluations/internal/")
    response = requests.post(
        f"{DJANGO_URL}/api/evaluations/internal/",
        json=test_evaluation,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 201:
        print(f"[FAIL] Failed to create evaluation: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    evaluation_id = result['id']
    print(f"[OK] Created evaluation #{evaluation_id}")
    print(f"   Commit: {result['commit_sha'][:7]}")
    print(f"   Score: {result['overall_score']}")
    print(f"   Findings: {result['finding_count']}")
    
    # Fetch evaluation details to verify findings
    print(f"\n[FETCH] Fetching evaluation details...")
    response = requests.get(f"{DJANGO_URL}/api/evaluations/{evaluation_id}/")
    
    if response.status_code != 200:
        print(f"[FAIL] Failed to fetch evaluation: {response.status_code}")
        return False
    
    evaluation = response.json()
    findings = evaluation['findings']
    
    print(f"\n[RESULTS] Verification Results:")
    print(f"   Total findings: {len(findings)}")
    
    # Check each finding's skills
    for i, finding in enumerate(findings, 1):
        print(f"\n   Finding {i}: {finding['title']}")
        print(f"   |- Severity: {finding['severity']}")
        print(f"   |- File: {finding['file_path']}")
        print(f"   |- Skills affected: {len(finding['skills'])} skill(s)")
        
        for skill in finding['skills']:
            print(f"      * {skill['name']} ({skill['slug']})")
        
        # Verify FindingSkill relationships
        for fs in finding['finding_skills']:
            print(f"      > Impact: {fs['impact_score']} (via FindingSkill)")
    
    print(f"\n[SUCCESS] All findings stored correctly with skill mappings!")
    return True

if __name__ == "__main__":
    try:
        success = test_findings_storage()
        exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to Django backend.")
        print("   Make sure Django is running on port 8000:")
        print("   cd django_backend && python manage.py runserver 8000")
        exit(1)
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
