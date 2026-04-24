"""
Tests for the One Submission → Many GradingSessions iteration model.

Covers the Leera "what happens after the teacher sends feedback?" loop:
  - synchronize on a POSTED session creates a new iteration
  - synchronize on a DRAFTED session is an in-place update
  - Submission.current_grading_session returns the non-superseded row
  - previous_iterations in the detail serializer
"""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    GradingSession,
    Rubric,
    Submission,
)
from grading.serializers import GradingSessionDetailSerializer
from grading.tests.test_webhooks import membership, make_pr_payload, post_webhook  # noqa: F401

User = get_user_model()


@pytest.mark.django_db
class TestSynchronizeNoLongerCreatesIteration:
    """Post-bugfix: synchronize is an in-place head_sha update only.
    Iterations are spawned by explicit intent signals (review_requested,
    student-submitted review, manual action)."""

    def test_no_iteration_on_synchronize_after_posted(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        assert iter1.iteration_number == 1

        # Teacher flow: flip iter1 to POSTED
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        # Student pushes → synchronize
        sync = make_pr_payload(action="synchronize")
        sync["pull_request"]["head"]["sha"] = "def456"
        resp = post_webhook(client, sync, delivery_id="d2")
        assert resp.status_code == 200

        # Crucial: synchronize alone must NOT spawn iter 2.
        assert GradingSession.objects.filter(submission=sub).count() == 1

    def test_no_iteration_on_merged_pr(self, membership):
        """Hard guard: if PR is merged (submission.graded), no event
        may spawn iterations."""
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        # Merge the PR
        merged = make_pr_payload(action="closed", state="closed", merged=True)
        post_webhook(client, merged, delivery_id="d-merge")
        sub.refresh_from_db()
        assert sub.status == Submission.Status.GRADED

        # Even review_requested after merge must not spawn iteration.
        from users.models import GitProviderConnection
        from grading.models import Course
        course = Course.objects.get(cohort=membership.cohort)
        teacher = course.owner
        GitProviderConnection.objects.create(
            user=teacher, provider="github", username="docentgh",
        )
        rr = make_pr_payload(action="review_requested")
        rr["pull_request"]["state"] = "closed"
        rr["requested_reviewer"] = {"login": "docentgh"}
        resp = post_webhook(client, rr, delivery_id="d-rr")
        assert resp.status_code == 200
        assert GradingSession.objects.filter(submission=sub).count() == 1


@pytest.mark.django_db
class TestSynchronizeInPlaceForNonTerminal:
    def test_synchronize_on_drafted_does_not_create_new_session(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.DRAFTED
        iter1.save(update_fields=["state"])

        sync = make_pr_payload(action="synchronize")
        sync["pull_request"]["head"]["sha"] = "def456"
        resp = post_webhook(client, sync, delivery_id="d2")
        assert resp.status_code == 200

        assert GradingSession.objects.filter(submission=sub).count() == 1
        iter1.refresh_from_db()
        assert iter1.iteration_number == 1
        assert iter1.superseded_by is None
        # Submission's head_sha/head_branch still update in place
        sub.refresh_from_db()

    def test_synchronize_on_pending_does_not_create_new_session(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        assert GradingSession.objects.filter(submission=sub).count() == 1

        sync = make_pr_payload(action="synchronize")
        post_webhook(client, sync, delivery_id="d2")
        assert GradingSession.objects.filter(submission=sub).count() == 1


def _spawn_iter2_via_helper(session):
    """Helper for legacy tests that previously relied on synchronize-triggered
    iteration. Post-bugfix, callers must go through create_next_iteration()."""
    from grading.webhooks import create_next_iteration
    return create_next_iteration(session)


@pytest.mark.django_db
class TestCurrentGradingSessionHelper:
    def test_current_grading_session_returns_non_superseded(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        _spawn_iter2_via_helper(iter1)

        current = sub.current_grading_session
        assert current is not None
        assert current.iteration_number == 2
        assert current.superseded_by is None

    def test_current_grading_session_with_single_session(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        current = sub.current_grading_session
        assert current is not None
        assert current.iteration_number == 1


@pytest.mark.django_db
class TestPreviousIterationsInSerializer:
    def test_previous_iterations_minimal_fields(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.ai_draft_scores = {"readability": {"score": 3}}
        iter1.final_scores = {"readability": {"score": 4}}
        iter1.save()

        _spawn_iter2_via_helper(iter1)
        iter2 = sub.current_grading_session

        data = GradingSessionDetailSerializer(iter2).data
        assert data["iteration_number"] == 2
        assert data["total_iterations"] == 2
        prior = data["previous_iterations"]
        assert len(prior) == 1
        p = prior[0]
        # Minimal shape — no heavy comment payloads
        assert set(p.keys()) == {
            "id",
            "iteration_number",
            "state",
            "eindbeoordeling",
            "posted_at",
            "created_at",
        }
        assert p["iteration_number"] == 1
        assert p["state"] == GradingSession.State.POSTED
        # final_scores takes precedence over draft scores
        assert p["eindbeoordeling"] == 4.0

    def test_single_iteration_has_empty_previous(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        session = GradingSession.objects.get(submission=sub)
        data = GradingSessionDetailSerializer(session).data
        assert data["iteration_number"] == 1
        assert data["total_iterations"] == 1
        assert data["previous_iterations"] == []


# ─────────────────────────────────────────────────────────────────────
# New-trigger tests (review_requested, pull_request_review submitted,
# review_thread resolved, manual start_new_iteration action).
# ─────────────────────────────────────────────────────────────────────

def _post_webhook_event(client, payload, *, event_type, delivery_id):
    return post_webhook(client, payload, delivery_id=delivery_id, event_type=event_type)


@pytest.mark.django_db
class TestReviewRequestedTrigger:
    def test_iteration_on_review_requested_teacher(self, membership):
        from users.models import GitProviderConnection
        from grading.models import Course
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        course = Course.objects.get(cohort=membership.cohort)
        GitProviderConnection.objects.create(
            user=course.owner, provider="github", username="docent-gh",
        )

        rr = make_pr_payload(action="review_requested")
        rr["requested_reviewer"] = {"login": "docent-gh"}
        resp = post_webhook(client, rr, delivery_id="d2")
        assert resp.status_code == 200

        sessions = list(GradingSession.objects.filter(submission=sub).order_by("iteration_number"))
        assert len(sessions) == 2
        assert sessions[1].iteration_number == 2
        assert sessions[1].state == GradingSession.State.PENDING

    def test_no_iteration_on_review_requested_non_teacher(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        rr = make_pr_payload(action="review_requested")
        rr["requested_reviewer"] = {"login": "some-other-student"}
        resp = post_webhook(client, rr, delivery_id="d2")
        assert resp.status_code == 200
        assert GradingSession.objects.filter(submission=sub).count() == 1


@pytest.mark.django_db
class TestPullRequestReviewTrigger:
    def _review_payload(self, *, reviewer_login, state="commented", body="Ready"):
        base = make_pr_payload(action="submitted")
        base["action"] = "submitted"
        base["review"] = {
            "user": {"login": reviewer_login},
            "state": state,
            "body": body,
        }
        return base

    def test_iteration_on_student_submitted_review(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        # Student (PR author) submits review on own PR.
        payload = self._review_payload(reviewer_login="jandeboer", body="Opnieuw kijken aub")
        resp = _post_webhook_event(
            client, payload, event_type="pull_request_review", delivery_id="d-pr-rev",
        )
        assert resp.status_code == 200
        assert GradingSession.objects.filter(submission=sub).count() == 2

    def test_no_iteration_on_teacher_submitted_review(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        payload = self._review_payload(reviewer_login="docent-gh", body="Prima werk")
        resp = _post_webhook_event(
            client, payload, event_type="pull_request_review", delivery_id="d-t-rev",
        )
        assert resp.status_code == 200
        # Teacher review = normal activity, not intent to re-review.
        assert GradingSession.objects.filter(submission=sub).count() == 1


@pytest.mark.django_db
class TestReviewThreadResolved:
    def test_thread_resolved_marks_posted_comment(self, membership):
        from grading.models import PostedComment
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        session = GradingSession.objects.get(submission=sub)

        # Seed a PostedComment row we can target.
        pc = PostedComment.objects.create(
            grading_session=session,
            client_mutation_id="mid-abc",
            github_comment_id=98765,
            file_path="app/models.py",
            line_number=42,
        )

        payload = {
            "action": "resolved",
            "thread": {"comments": [{"id": 98765}]},
            "pull_request": {"user": {"login": "jandeboer"}, "state": "open"},
            "sender": {"login": "jandeboer"},
            "repository": {"full_name": "jandeboer/assignment-q3"},
        }
        resp = _post_webhook_event(
            client, payload,
            event_type="pull_request_review_thread", delivery_id="d-resolve",
        )
        assert resp.status_code == 200
        pc.refresh_from_db()
        assert pc.resolved_at is not None
        assert pc.resolved_by_student is True


@pytest.mark.django_db
class TestManualStartNewIterationAction:
    def _login_teacher(self, client, membership):
        from grading.models import Course
        course = Course.objects.get(cohort=membership.cohort)
        client.force_authenticate(user=course.owner)
        return course.owner

    def test_manual_start_new_iteration_action(self, membership):
        from grading.models import PostedComment
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        # Seed activity signal: a resolved thread.
        PostedComment.objects.create(
            grading_session=iter1,
            client_mutation_id="mid-res",
            github_comment_id=1,
            file_path="a.py",
            line_number=1,
            resolved_at=iter1.created_at,
            resolved_by_student=True,
        )

        self._login_teacher(client, membership)
        resp = client.post(f"/api/grading/sessions/{iter1.id}/start_new_iteration/", {})
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert data["iteration_number"] == 2
        iter2 = GradingSession.objects.get(pk=data["session_id"])
        assert iter2.state == GradingSession.State.PENDING
        assert iter2.iteration_number == 2

    def test_manual_start_new_iteration_disabled_on_merged(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        sub.status = Submission.Status.GRADED
        sub.save(update_fields=["status"])

        self._login_teacher(client, membership)
        resp = client.post(f"/api/grading/sessions/{iter1.id}/start_new_iteration/", {})
        assert resp.status_code == 400
