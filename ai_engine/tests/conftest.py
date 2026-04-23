"""
Shared pytest fixtures for ReviewHub AI Engine tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm_response():
    """Mock LLM evaluation response with realistic findings."""
    return {
        "overall_score": 65.0,
        "findings": [
            {
                "title": "SQL Injection vulnerability",
                "description": "Using string concatenation in SQL query allows injection attacks.",
                "severity": "critical",
                "difficulty": "moderate",
                "file_path": "app/db.py",
                "line_start": 42,
                "line_end": 42,
                "original_code": 'cursor.execute("SELECT * FROM users WHERE id = " + user_id)',
                "suggested_code": (
                    'def get_user(cursor, user_id):\n'
                    '    """Fetch user by ID using parameterized query."""\n'
                    '    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))\n'
                    '    return cursor.fetchone()'
                ),
                "explanation": "String concatenation in SQL allows attackers to inject malicious SQL.",
                "skills_affected": ["input_validation", "database_queries"],
            }
        ],
    }


@pytest.fixture
def mock_django_client():
    """Mock DjangoClient for AI engine tests."""
    client = AsyncMock()
    client.get_user_by_email.return_value = {"id": 1, "email": "dev@test.com"}
    client.get_project_member_by_email.return_value = None
    client.get_org_llm_config.return_value = None
    client.get_adaptive_profile.return_value = {}
    client.create_evaluation.return_value = {"id": 1}
    return client


@pytest.fixture
def sample_webhook_payload():
    """Sample GitHub push webhook payload."""
    return {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": "abc123def456abc123def456abc123def456abc123",
        "pusher": {"name": "testdev", "email": "dev@test.com"},
        "repository": {
            "id": 1,
            "name": "testrepo",
            "full_name": "testorg/testrepo",
            "html_url": "https://github.com/testorg/testrepo",
            "clone_url": "https://github.com/testorg/testrepo.git",
            "default_branch": "main",
        },
        "head_commit": {
            "id": "abc123def456abc123def456abc123def456abc123",
            "message": "feat: add user login",
            "timestamp": "2026-04-15T12:00:00Z",
            "author": {"name": "testdev", "email": "dev@test.com"},
            "added": [],
            "removed": [],
            "modified": ["app/db.py"],
        },
        "commits": [
            {
                "id": "abc123def456abc123def456abc123def456abc123",
                "message": "feat: add user login",
                "timestamp": "2026-04-15T12:00:00Z",
                "author": {"name": "testdev", "email": "dev@test.com"},
                "added": [],
                "removed": [],
                "modified": ["app/db.py"],
            }
        ],
        "sender": {"login": "testdev"},
    }
