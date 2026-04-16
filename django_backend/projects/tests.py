"""
Tests for ReviewHub projects app.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from projects.models import Project


# ── P3-7: Webhook URL is configurable ────────────────────────────────────

class TestWebhookUrlConfigurable(TestCase):
    """P3-7: Webhook URL uses WEBHOOK_BASE_URL, not hardcoded ngrok."""

    def test_webhook_callback_url_uses_env(self):
        """_webhook_callback_url should use WEBHOOK_BASE_URL env var."""
        from unittest.mock import patch
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            email="dev@test.com", username="testdev", password="pass123"
        )
        project = Project.objects.create(
            name="Test", repo_owner="org", repo_name="repo",
            provider="github", created_by=user,
        )

        with patch.dict('os.environ', {'WEBHOOK_BASE_URL': 'https://reviewhub.example.com'}):
            from batch.webhook_setup import _webhook_callback_url
            url = _webhook_callback_url(project)
            self.assertIn("reviewhub.example.com", url)
            self.assertNotIn("ngrok", url)
            self.assertIn(f"/api/v1/webhook/github/{project.id}", url)

    def test_webhook_url_no_ngrok_in_env(self):
        """FASTAPI_URL in .env should not contain ngrok."""
        from django.conf import settings
        fastapi_url = getattr(settings, 'FASTAPI_URL', '')
        self.assertNotIn("ngrok", fastapi_url,
                         "FASTAPI_URL should not be an ngrok URL in default config")
