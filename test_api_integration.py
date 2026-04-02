#!/usr/bin/env python3
"""
Test script to verify Django API endpoints match frontend expectations.
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_login():
    """Test login endpoint."""
    print("\n🔐 Testing login endpoint...")
    response = requests.post(
        f"{BASE_URL}/auth/token/",
        json={"email": "test@reviewhub.dev", "password": "testpass123"},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Login successful!")
        print(f"   Access token: {data.get('access', 'N/A')[:50]}...")
        print(f"   Refresh token: {data.get('refresh', 'N/A')[:50]}...")
        return data.get('access')
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def test_me(token):
    """Test /users/me/ endpoint."""
    print("\n👤 Testing /users/me/ endpoint...")
    response = requests.get(
        f"{BASE_URL}/users/me/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ User profile retrieved!")
        print(f"   Email: {data.get('email')}")
        print(f"   Role: {data.get('role')}")
        print(f"   Username: {data.get('username')}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Response: {response.text}")

def test_projects(token):
    """Test /projects/ endpoint."""
    print("\n📁 Testing /projects/ endpoint...")
    response = requests.get(
        f"{BASE_URL}/projects/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Projects retrieved!")
        print(f"   Count: {len(data.get('results', data))}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Response: {response.text}")

def test_evaluations(token):
    """Test /evaluations/ endpoint."""
    print("\n📊 Testing /evaluations/ endpoint...")
    response = requests.get(
        f"{BASE_URL}/evaluations/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Evaluations retrieved!")
        print(f"   Count: {len(data.get('results', data))}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Response: {response.text}")

def test_skills(token):
    """Test /skills/ endpoints."""
    print("\n🎯 Testing /skills/categories/ endpoint...")
    response = requests.get(
        f"{BASE_URL}/skills/categories/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Skill categories retrieved!")
        print(f"   Count: {len(data)}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Response: {response.text}")

def test_health():
    """Test health endpoint."""
    print("\n💚 Testing /health/ endpoint...")
    response = requests.get(f"{BASE_URL}/health/")
    
    if response.status_code == 200:
        print(f"✅ Health check passed!")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Failed: {response.status_code}")

if __name__ == "__main__":
    print("=" * 60)
    print("ReviewHub v2 - API Integration Test")
    print("=" * 60)
    
    # Test health first
    test_health()
    
    # Test authentication flow
    token = test_login()
    
    if token:
        test_me(token)
        test_projects(token)
        test_evaluations(token)
        test_skills(token)
    
    print("\n" + "=" * 60)
    print("✨ Integration test complete!")
    print("=" * 60)
