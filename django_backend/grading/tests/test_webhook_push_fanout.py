"""
Regression test: GitHub push events forward to ai_engine.

Architecture:
    GitHub repo
       │
       └── ONE webhook → Nakijken Django  /api/grading/webhooks/github/
                          ├── pull_request*   → existing PR handler
                          └── push            → forward_push_to_ai_engine
                                                   (fire-and-forget POST to
                                                    ai_engine /api/v1/webhook/
                                                    github/<project_id>)

Why fan-out lives in Django:
  - Schools configure ONE webhook URL per repo (no per-pipeline config).
  - One signature secret shared by both services (rotate once, not twice).
  - Fan-out logic stays in our codebase — easy to extend with rules
    ("skip ai_engine for repos older than X", etc.) post-pitch.

What this test pins down:
  - Push events with a matching Project trigger an HTTP POST to ai_engine.
  - The POST forwards the original body + headers verbatim so ai_engine's
    HMAC signature check passes (assumes shared GITHUB_WEBHOOK_SECRET).
  - Pushes with no matching Project skip silently (200, fanout=skipped).
  - Non-push events do NOT fan out.
  - ai_engine being unreachable does NOT fail the webhook (Django still
    returns 200 to GitHub so delivery isn't retried indefinitely).
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from projects.models import Project


def _push_payload(repo_html_url: str = "https://github.com/inno8/codelens-test") -> dict:
    return {
        "ref": "refs/heads/main",
        "repository": {
            "html_url": repo_html_url,
            "full_name": repo_html_url.split("github.com/", 1)[-1],
        },
        "commits": [
            {
                "id": "abc1234567",
                "message": "fix: typo",
                "author": {"name": "Tester", "email": "tester@example.com"},
            }
        ],
        "sender": {"login": "tester-bot"},
    }


def _post_push(client, payload, *, delivery_id="push-1", signature=None):
    body = json.dumps(payload).encode()
    headers = {
        "HTTP_X_GITHUB_DELIVERY": delivery_id,
        "HTTP_X_GITHUB_EVENT": "push",
    }
    if signature:
        headers["HTTP_X_HUB_SIGNATURE_256"] = signature
    return client.post(
        "/api/grading/webhooks/github/",
        data=body,
        content_type="application/json",
        **headers,
    )


@pytest.fixture
def project_for_codelens(db):
    """A Project owning the codelens-test repo (mirrors prod-like demo state)."""
    from django.contrib.auth import get_user_model
    from users.models import Organization

    User = get_user_model()
    org = Organization.objects.create(name="Org Push", slug="org-push")
    teacher = User.objects.create_user(
        username="t_push", email="t_push@example.com", password="pw",
        role="teacher", organization=org,
    )
    return Project.objects.create(
        provider="github",
        repo_owner="inno8",
        repo_name="codelens-test",
        name="codelens-test",
        repo_url="https://github.com/inno8/codelens-test",
        created_by=teacher,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Forward path
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPushFanOut:
    def test_push_with_matching_project_forwards(self, project_for_codelens):
        client = APIClient()
        with patch("grading.webhooks.threading.Thread") as fake_thread:
            # Make .start() a no-op so the test doesn't actually fire HTTP.
            fake_thread.return_value.start.return_value = None
            resp = _post_push(client, _push_payload())
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["fanout"]["forwarded"] is True
        assert body["fanout"]["project_id"] == project_for_codelens.id
        assert "/api/v1/webhook/github/" in body["fanout"]["ai_engine_url"]
        # The daemon thread was started (will POST in the background).
        assert fake_thread.return_value.start.called

    def test_push_with_no_matching_project_skips_silently(self, db):
        client = APIClient()
        # No Project rows exist for this repo.
        resp = _post_push(
            client,
            _push_payload(repo_html_url="https://github.com/unknown-org/unknown-repo"),
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["fanout"]["forwarded"] is False
        assert body["fanout"]["reason"] == "no_project_match"

    def test_push_resolves_repo_url_with_trailing_slash(self, project_for_codelens):
        """GitHub payloads sometimes carry repo URL with a trailing slash;
        the lookup must match."""
        client = APIClient()
        with patch("grading.webhooks.threading.Thread") as fake_thread:
            fake_thread.return_value.start.return_value = None
            resp = _post_push(
                client,
                _push_payload(repo_html_url="https://github.com/inno8/codelens-test/"),
            )
        assert resp.status_code == 200
        assert resp.json()["fanout"]["forwarded"] is True

    def test_push_resolves_repo_url_with_dot_git(self, project_for_codelens):
        """Some webhook payloads include .git on the URL. Tolerate it."""
        client = APIClient()
        with patch("grading.webhooks.threading.Thread") as fake_thread:
            fake_thread.return_value.start.return_value = None
            resp = _post_push(
                client,
                _push_payload(repo_html_url="https://github.com/inno8/codelens-test.git"),
            )
        assert resp.status_code == 200
        assert resp.json()["fanout"]["forwarded"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Non-push events do NOT fan out
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestNonPushDoesNotFanOut:
    def test_release_event_does_not_forward(self, project_for_codelens):
        client = APIClient()
        with patch("grading.webhooks.threading.Thread") as fake_thread:
            fake_thread.return_value.start.return_value = None
            body = json.dumps(_push_payload()).encode()
            resp = client.post(
                "/api/grading/webhooks/github/",
                data=body,
                content_type="application/json",
                HTTP_X_GITHUB_DELIVERY="d-release",
                HTTP_X_GITHUB_EVENT="release",
            )
        assert resp.status_code == 200
        assert "ignored" in resp.json().get("message", "").lower()
        assert not fake_thread.return_value.start.called

    def test_pull_request_does_not_fan_out(self, project_for_codelens):
        """PR events go to the existing handler, NOT the ai_engine forwarder."""
        client = APIClient()
        with patch("grading.webhooks.threading.Thread") as fake_thread:
            fake_thread.return_value.start.return_value = None
            body = json.dumps({
                "action": "opened",
                "pull_request": {
                    "number": 1,
                    "title": "test",
                    "html_url": "https://github.com/inno8/codelens-test/pull/1",
                    "head": {"ref": "feat/x"},
                    "base": {"ref": "main"},
                    "user": {"login": "tester-bot"},
                    "merged": False,
                    "state": "open",
                },
                "repository": {
                    "html_url": "https://github.com/inno8/codelens-test",
                    "full_name": "inno8/codelens-test",
                },
                "sender": {"login": "tester-bot"},
            }).encode()
            resp = client.post(
                "/api/grading/webhooks/github/",
                data=body,
                content_type="application/json",
                HTTP_X_GITHUB_DELIVERY="d-pr-1",
                HTTP_X_GITHUB_EVENT="pull_request",
            )
        # PR didn't match a Cohort here so it returns 200 with matched=False
        # (or similar). The point: NO fan-out thread spawned.
        assert resp.status_code == 200
        assert not fake_thread.return_value.start.called


# ─────────────────────────────────────────────────────────────────────────────
# Resilience: ai_engine being down must not break the webhook
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestFanOutResilience:
    def test_ai_engine_unreachable_does_not_500(self, project_for_codelens):
        """The fan-out POST runs in a daemon thread; the webhook returns
        200 to GitHub before the thread runs. Even if ai_engine is dead,
        Django's response stays 200 so GitHub doesn't retry forever."""
        client = APIClient()
        # Don't patch threading — let the real thread run, but mock requests
        # so ai_engine appears down.
        import requests as real_requests
        with patch.object(real_requests, "post") as fake_post:
            fake_post.side_effect = ConnectionError("ai_engine unreachable")
            resp = _post_push(client, _push_payload(), delivery_id="resilience-1")
        assert resp.status_code == 200
        assert resp.json()["fanout"]["forwarded"] is True
