"""
Tests for grading.webhooks.github_webhook.

Covers:
  - Signature verification (when GITHUB_WEBHOOK_SECRET is set)
  - Delivery-id dedupe (GitHub retries → second delivery returns 200+deduped)
  - No classroom match → 200 but matched=false (not an error from GitHub's POV)
  - PR opened → creates Submission + GradingSession in PENDING
  - PR synchronize → updates existing Submission (new head branch/sha)
  - PR closed merged → Submission.status = GRADED
  - Ignored events (non-pull_request) and ignored actions (labeled, assigned)
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    GradingSession,
    Rubric,
    Submission,
    WebhookDelivery,
)

User = get_user_model()


@pytest.fixture
def membership(db):
    """A cohort + course with one student linked to jandeboer/assignment-q3."""
    from users.models import GitProviderConnection, Organization

    org = Organization.objects.create(name="Media College", slug="media-college")
    teacher = User.objects.create_user(
        username="docent", email="docent@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="jandeboer", email="jan@ex.com", password="pw",
        role="developer", organization=org,
    )
    GitProviderConnection.objects.create(
        user=student, provider="github", username="jandeboer",
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="Seed",
        criteria=[
            {"id": "readability", "name": "Readability", "weight": 1,
             "levels": [{"score": 1}, {"score": 4}]}
        ],
    )
    cohort = Cohort.objects.create(org=org, name="MBO-4 ICT Y2 (klas)")
    Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="MBO-4 ICT Y2", rubric=rubric,
    )
    m = CohortMembership.objects.create(
        cohort=cohort,
        student=student,
        student_repo_url="https://github.com/jandeboer/assignment-q3",
    )
    return m


def make_pr_payload(
    *, action: str = "opened", pr_number: int = 1, merged: bool = False,
    state: str = "open", author: str = "jandeboer",
    repo_full_name: str = "jandeboer/assignment-q3",
):
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "state": state,
            "merged": merged,
            "title": "Fix null handling",
            "html_url": f"https://github.com/{repo_full_name}/pull/{pr_number}",
            "head": {"ref": "feat/null-fix", "sha": "abc123"},
            "base": {"ref": "main"},
            "user": {"login": author},
        },
        "repository": {
            "full_name": repo_full_name,
            "html_url": f"https://github.com/{repo_full_name}",
        },
    }


def post_webhook(
    client: APIClient, payload: dict, *,
    delivery_id: str = "delivery-1",
    event_type: str = "pull_request",
    signature: str | None = None,
):
    body = json.dumps(payload).encode()
    headers = {
        "HTTP_X_GITHUB_DELIVERY": delivery_id,
        "HTTP_X_GITHUB_EVENT": event_type,
    }
    if signature:
        headers["HTTP_X_HUB_SIGNATURE_256"] = signature
    return client.post(
        "/api/grading/webhooks/github/",
        data=body,
        content_type="application/json",
        **headers,
    )


@pytest.mark.django_db
class TestWebhookMatching:
    def test_pr_opened_creates_submission_and_session(self, membership):
        client = APIClient()
        resp = post_webhook(client, make_pr_payload(action="opened"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["session_created"] is True

        course = Course.objects.get(cohort=membership.cohort)
        sub = Submission.objects.get(course=course, pr_number=1)
        assert sub.repo_full_name == "jandeboer/assignment-q3"
        assert sub.head_branch == "feat/null-fix"
        assert sub.status == Submission.Status.OPEN

        session = GradingSession.objects.get(submission=sub)
        assert session.state == GradingSession.State.PENDING
        assert session.rubric == course.rubric

    def test_pr_synchronize_updates_existing_submission(self, membership):
        client = APIClient()
        # First: open
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")

        # Second: synchronize with a new head sha/branch
        sync_payload = make_pr_payload(action="synchronize")
        sync_payload["pull_request"]["head"]["sha"] = "def456"
        sync_payload["pull_request"]["head"]["ref"] = "feat/updated"
        resp = post_webhook(client, sync_payload, delivery_id="d2")
        assert resp.status_code == 200

        # Still one submission, but updated
        course = Course.objects.get(cohort=membership.cohort)
        assert Submission.objects.filter(course=course).count() == 1
        sub = Submission.objects.get(course=course)
        assert sub.head_branch == "feat/updated"

        # Session still exists (not duplicated)
        assert GradingSession.objects.filter(submission=sub).count() == 1

    def test_pr_closed_merged_marks_submission_graded(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        close_payload = make_pr_payload(action="closed", state="closed", merged=True)
        resp = post_webhook(client, close_payload, delivery_id="d2")
        assert resp.status_code == 200
        course = Course.objects.get(cohort=membership.cohort)
        sub = Submission.objects.get(course=course)
        assert sub.status == Submission.Status.GRADED

    def test_no_cohort_match_returns_ok_unmatched(self, membership):
        client = APIClient()
        # Different repo — no membership for it
        payload = make_pr_payload(repo_full_name="someone/random-repo")
        resp = post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["matched"] is False
        assert Submission.objects.count() == 0

    def test_matches_via_git_connection_when_repo_url_mismatches(self, membership):
        """If membership.student_repo_url isn't set but the PR author's
        GitHub handle matches a GitProviderConnection, we still match."""
        client = APIClient()
        # Clear the explicit repo URL → force the rule-2 fallback
        membership.student_repo_url = ""
        membership.save(update_fields=["student_repo_url"])
        # PR author login matches the GitProviderConnection
        resp = post_webhook(client, make_pr_payload(author="jandeboer"))
        assert resp.status_code == 200
        assert resp.json()["matched"] is True


@pytest.mark.django_db
class TestWebhookDedupe:
    def test_second_delivery_is_deduped(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(), delivery_id="same-id")
        resp = post_webhook(client, make_pr_payload(), delivery_id="same-id")
        assert resp.status_code == 200
        assert resp.json().get("deduped") is True
        # Only one submission created despite two deliveries
        course = Course.objects.get(cohort=membership.cohort)
        assert Submission.objects.filter(course=course).count() == 1

    def test_delivery_record_persisted(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(), delivery_id="persist-me")
        assert WebhookDelivery.objects.filter(
            provider="github", delivery_id="persist-me",
        ).exists()


@pytest.mark.django_db
class TestWebhookIgnoredEvents:
    def test_non_pull_request_event_is_ignored(self, membership):
        # Push events get forwarded to ai_engine (see test_webhook_push_fanout).
        # `release` is a real GitHub event that Nakijken still doesn't care
        # about — useful as the canonical "ignored" case.
        client = APIClient()
        resp = post_webhook(
            client, make_pr_payload(),
            event_type="release",
            delivery_id="d-release",
        )
        assert resp.status_code == 200
        assert "ignored" in resp.json()["message"].lower()
        assert Submission.objects.count() == 0

    def test_uninteresting_action_is_ignored(self, membership):
        client = APIClient()
        resp = post_webhook(
            client, make_pr_payload(action="labeled"),
            delivery_id="d-label",
        )
        assert resp.status_code == 200
        assert "ignored" in resp.json()["message"].lower()
        assert Submission.objects.count() == 0


@pytest.mark.django_db
class TestSignatureVerification:
    def _sign(self, body: bytes, secret: str) -> str:
        mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={mac}"

    @override_settings(GITHUB_WEBHOOK_SECRET="test-secret-42")
    def test_valid_signature_accepted(self, membership):
        client = APIClient()
        payload = make_pr_payload()
        body = json.dumps(payload).encode()
        sig = self._sign(body, "test-secret-42")
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="d-sig-ok",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        assert resp.status_code == 200

    @override_settings(GITHUB_WEBHOOK_SECRET="test-secret-42")
    def test_invalid_signature_rejected(self, membership):
        client = APIClient()
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=json.dumps(make_pr_payload()).encode(),
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="d-sig-bad",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_HUB_SIGNATURE_256="sha256=totallywrong",
        )
        assert resp.status_code == 403

    def test_missing_secret_bypasses_signature_check(self, membership):
        """v1 dev convenience: no signature required if no secret set."""
        client = APIClient()
        resp = post_webhook(client, make_pr_payload())
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWebhookMalformed:
    def test_malformed_json_returns_400(self, db):
        client = APIClient()
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=b"not-json",
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="d-bad",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 400

    def test_missing_repository_returns_400(self, db):
        client = APIClient()
        body = {"action": "opened", "pull_request": {"number": 1}}
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=json.dumps(body).encode(),
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="d-norepo",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestWebhookParseFailureDoesNotBurnDeliveryId:
    """Regression: if payload parsing fails, the delivery guid must NOT be
    persisted to WebhookDelivery — otherwise GitHub's redelivery of the
    corrected payload gets dedup-skipped and the teacher never sees the PR."""

    def test_invalid_json_does_not_create_delivery_row(self, db):
        client = APIClient()
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=b"{not valid json",
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="burn-me",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 400
        assert not WebhookDelivery.objects.filter(
            provider="github", delivery_id="burn-me",
        ).exists()

    def test_redelivery_after_failure_is_processed_normally(self, membership):
        client = APIClient()
        # First attempt: garbage body → 400, no WebhookDelivery row.
        bad = client.post(
            "/api/grading/webhooks/github/",
            data=b"\xff\xfe not utf8 json",
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="retry-guid",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert bad.status_code == 400
        assert WebhookDelivery.objects.count() == 0

        # GitHub redelivers with a corrected payload, same delivery guid.
        good = post_webhook(
            client, make_pr_payload(action="opened"),
            delivery_id="retry-guid",
        )
        assert good.status_code == 200
        data = good.json()
        assert data["matched"] is True
        assert data["session_created"] is True
        assert WebhookDelivery.objects.filter(delivery_id="retry-guid").count() == 1


@pytest.mark.django_db
class TestWebhookFormEncodedContentType:
    """Regression: GitHub supports application/x-www-form-urlencoded with a
    `payload=<url-encoded-json>` field. Must be parsed identically to JSON."""

    def test_form_encoded_webhook_is_processed(self, membership):
        from urllib.parse import urlencode

        client = APIClient()
        payload = make_pr_payload(action="opened")
        body = urlencode({"payload": json.dumps(payload)}).encode()
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=body,
            content_type="application/x-www-form-urlencoded",
            HTTP_X_GITHUB_DELIVERY="form-1",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["matched"] is True
        assert data["session_created"] is True

    def test_form_encoded_missing_payload_field_returns_400(self, db):
        client = APIClient()
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=b"not_payload=something",
            content_type="application/x-www-form-urlencoded",
            HTTP_X_GITHUB_DELIVERY="form-bad",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 400
        assert not WebhookDelivery.objects.filter(delivery_id="form-bad").exists()

    def test_unsupported_content_type_returns_400(self, db):
        client = APIClient()
        resp = client.post(
            "/api/grading/webhooks/github/",
            data=b"<xml/>",
            content_type="application/xml",
            HTTP_X_GITHUB_DELIVERY="xml-1",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 400
