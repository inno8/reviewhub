"""
Test script for dashboard API endpoints
"""
import requests
import json
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"

# First, check if we can access the API
def test_health():
    print("[TEST] Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    print()

def test_dashboard_endpoints(token=None):
    """Test all dashboard endpoints"""
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    endpoints = [
        '/api/skills/dashboard/overview/',
        '/api/skills/dashboard/skills/',
        '/api/skills/dashboard/progress/',
        '/api/skills/dashboard/recent/',
    ]
    
    print("[TEST] Testing Dashboard API Endpoints...")
    print(f"   Auth token: {'[OK] Provided' if token else '[NONE] None (may need auth)'}")
    print()
    
    for endpoint in endpoints:
        print(f"[ENDPOINT] {endpoint}")
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] Success")
                print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
            elif response.status_code == 401:
                print(f"   [AUTH] Unauthorized (needs authentication)")
            else:
                print(f"   [ERROR] {response.text[:200]}")
        except Exception as e:
            print(f"   [EXCEPTION] {str(e)}")
        print()

if __name__ == "__main__":
    test_health()
    
    print("=" * 60)
    print("Note: Dashboard endpoints require authentication.")
    print("If you have a valid JWT token, you can pass it to test_dashboard_endpoints()")
    print("=" * 60)
    print()
    
    # Test without auth (will show 401 errors, which is expected)
    test_dashboard_endpoints()
    
    print("[DONE] API structure test complete!")
    print("To fully test, log in via the frontend and use the browser DevTools")
    print("to capture your JWT token from localStorage.")
