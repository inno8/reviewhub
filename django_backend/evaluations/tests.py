"""
Tests for ReviewHub evaluations app.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from evaluations.models import Evaluation, Finding, FindingSkill


# ── P1-1: httpx dependency installed ──────────────────────────────────────

class TestCheckUnderstandingEndpoint(TestCase):
    """P1-1: Verify check-understanding endpoint works (httpx installed)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from projects.models import Project, ProjectMember
        from skills.models import SkillCategory, Skill

        User = get_user_model()
        self.user = User.objects.create_user(
            email="dev@test.com",
            username="testdev",
            password="testpass123",
        )
        self.project = Project.objects.create(
            name="Test Project",
            repo_owner="testorg",
            repo_name="testrepo",
            created_by=self.user,
        )
        self.evaluation = Evaluation.objects.create(
            project=self.project,
            author=self.user,
            commit_sha="abc123",
            branch="main",
            author_name="testdev",
            author_email="dev@test.com",
            overall_score=65.0,
            status="completed",
        )
        self.finding = Finding.objects.create(
            evaluation=self.evaluation,
            title="SQL Injection vulnerability",
            description="Using string concatenation in SQL query",
            severity="critical",
            file_path="app/db.py",
            line_start=42,
            line_end=42,
            original_code='cursor.execute("SELECT * FROM users WHERE id = " + user_id)',
            suggested_code='cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))',
            explanation="String concatenation in SQL allows attackers to inject malicious SQL.",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("httpx.post")
    def test_check_understanding_returns_200(self, mock_httpx_post):
        """P1-1: check-understanding should return 200, not 500."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "level": "got_it",
            "feedback": "Good understanding!",
            "deeper_explanation": "",
        }
        mock_httpx_post.return_value = mock_response

        response = self.client.post(
            "/api/evaluations/findings/check-understanding/",
            data={
                "findings": [
                    {
                        "id": self.finding.id,
                        "explanation": (
                            "SQL injection happens when user input is concatenated directly "
                            "into a SQL string. An attacker can end the intended query and "
                            "execute their own SQL commands, potentially reading or deleting "
                            "all data in the database."
                        ),
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content}"
        results = response.json()
        assert "results" in results or isinstance(results, list)

    def test_httpx_is_importable(self):
        """P1-1: httpx module must be importable (dependency installed)."""
        import httpx
        assert hasattr(httpx, "post")


# ── P1-3: DEBUG=false returns JSON, not HTML stack traces ─────────────────

from django.test import override_settings

@override_settings(DEBUG=False)
class TestDebugMode(TestCase):
    """P1-3: Verify 404s return clean JSON, not Django debug pages."""

    def test_404_returns_json_not_html(self):
        """Non-existent endpoint should return JSON error, not HTML debug page."""
        client = APIClient()
        response = client.get("/api/this-endpoint-does-not-exist/")

        assert response.status_code == 404
        content_type = response.get("Content-Type", "")
        assert "application/json" in content_type, (
            f"Expected JSON response, got Content-Type: {content_type}"
        )
        # Must not contain Django debug HTML
        body = response.content.decode("utf-8", errors="replace")
        assert "<html" not in body.lower(), "Response contains HTML — DEBUG may be True"
        assert "Traceback" not in body, "Response contains traceback — DEBUG may be True"
