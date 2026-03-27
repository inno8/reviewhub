#!/usr/bin/env python
"""
Create a test user and get an auth token
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Try to register a test user
register_data = {
    "email": "test@reviewhub.dev",
    "username": "testuser",
    "password": "testpass123",
    "password2": "testpass123",
    "full_name": "Test User"
}

print("[1] Attempting to register test user...")
response = requests.post(f"{BASE_URL}/api/users/register/", json=register_data)
print(f"    Status: {response.status_code}")
if response.status_code in [200, 201]:
    print(f"    [OK] User created successfully")
elif response.status_code == 400:
    print(f"    [INFO] User might already exist: {response.json()}")
else:
    print(f"    Response: {response.text}")

# Try to get a token
print("\n[2] Attempting to get auth token...")
token_data = {
    "email": "test@reviewhub.dev",
    "password": "testpass123"
}

response = requests.post(f"{BASE_URL}/api/auth/token/", json=token_data)
print(f"    Status: {response.status_code}")

if response.status_code == 200:
    token_response = response.json()
    access_token = token_response.get('access')
    print(f"    [OK] Token obtained successfully")
    print(f"\n[TOKEN]")
    print(f"{access_token}")
    
    # Save to file for later use
    with open('test_token.txt', 'w') as f:
        f.write(access_token)
    print(f"\n    Saved to test_token.txt")
else:
    print(f"    [ERROR] Failed to get token")
    print(f"    Response: {response.text}")
