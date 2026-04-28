"""
Shared fixtures for ReviewHub integration tests.
These tests hit running services (Django on 8000, FastAPI on 8001).
"""
import os
import pytest
import requests

DJANGO_URL = os.environ.get("REVIEWHUB_DJANGO_URL", "http://localhost:8000")
FASTAPI_URL = os.environ.get("REVIEWHUB_FASTAPI_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
def django_url():
    return DJANGO_URL


@pytest.fixture(scope="session")
def fastapi_url():
    return FASTAPI_URL


@pytest.fixture(scope="session")
def auth_token(django_url):
    """Get JWT token for integration tests. Uses tester account."""
    resp = requests.post(
        f"{django_url}/api/auth/token/",
        json={"email": "tester@reviewhub.com", "password": "tester123"},
        timeout=10,
    )
    if resp.status_code != 200:
        pytest.skip("Cannot authenticate — is Django running with test user?")
    return resp.json()["access"]


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers for API requests."""
    return {"Authorization": f"Bearer {auth_token}"}
