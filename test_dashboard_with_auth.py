#!/usr/bin/env python
"""
Test dashboard endpoints with authentication
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Read token from file
with open('test_token.txt', 'r') as f:
    token = f.read().strip()

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

endpoints = [
    '/api/skills/dashboard/overview/',
    '/api/skills/dashboard/skills/',
    '/api/skills/dashboard/progress/',
    '/api/skills/dashboard/recent/',
]

print("=" * 60)
print("TESTING DASHBOARD API ENDPOINTS")
print("=" * 60)

for endpoint in endpoints:
    print(f"\n[ENDPOINT] {endpoint}")
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        print(f"    Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"    [OK] Success")
            print(f"    Response structure:")
            if isinstance(data, dict):
                for key in data.keys():
                    print(f"      - {key}: {type(data[key]).__name__}")
            elif isinstance(data, list):
                print(f"      - List with {len(data)} items")
                if len(data) > 0:
                    print(f"      - First item keys: {list(data[0].keys())}")
            print(f"    Data: {json.dumps(data, indent=2)[:500]}...")
        else:
            print(f"    [ERROR] Failed")
            print(f"    Response: {response.text[:200]}")
    except Exception as e:
        print(f"    [EXCEPTION] {str(e)}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
