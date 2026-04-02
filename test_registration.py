#!/usr/bin/env python
"""Test user registration endpoint"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'django_backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()

from users.models import User
from django.test import Client

# Create test client
client = Client()

# Test registration
print("Testing user registration...")
response = client.post('/api/users/register/', {
    'email': 'testuser@example.com',
    'username': 'testuser',
    'password': 'testpass123',
    'first_name': 'Test',
    'last_name': 'User'
}, content_type='application/json')

print(f"Status: {response.status_code}")
if response.status_code == 201:
    print("✅ Registration successful!")
    data = response.json()
    print(f"User: {data.get('user', {}).get('email')}")
    print(f"Tokens: {'access' in data.get('tokens', {})}")
else:
    print(f"❌ Registration failed: {response.content.decode()}")

# Clean up
try:
    User.objects.filter(email='testuser@example.com').delete()
    print("✅ Test user cleaned up")
except Exception as e:
    print(f"Cleanup warning: {e}")
