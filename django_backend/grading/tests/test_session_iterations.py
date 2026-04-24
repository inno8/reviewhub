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
class TestSynchronizeCreatesIteration:
    def test_synchronize_after_posted_creates_new_iteration(self, membership):
        client = APIClient()
        # 1. opened → iteration 1 PENDING
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        assert iter1.iteration_number == 1
        assert iter1.superseded_by is None

        # 2. simulate teacher flow: flip iter1 to POSTED.
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        # 3. student pushes new commits → synchronize webhook.
        sync = make_pr_payload(action="synchronize")
        sync["pull_request"]["head"]["sha"] = "def456"
        resp = post_webhook(client, sync, delivery_id="d2")
        assert resp.status_code == 200

        sessions = list(
            GradingSession.objects.filter(submission=sub).order_by("iteration_number")
        )
        assert len(sessions) == 2, "synchronize after POSTED should have spawned iter 2"
        iter1.refresh_from_db()
        iter2 = sessions[1]

        assert iter2.iteration_number == 2
        assert iter2.state == GradingSession.State.PENDING
        assert iter2.ai_draft_scores == {}
        assert iter2.ai_draft_comments == []
        assert iter2.final_scores == {}
        assert iter1.superseded_by_id == iter2.id

    def test_synchronize_after_partial_also_creates_new_iteration(self, membership):
        """PARTIAL is also a terminal state for iteration purposes."""
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.PARTIAL
        iter1.save(update_fields=["state"])

        sync = make_pr_payload(action="synchronize")
        resp = post_webhook(client, sync, delivery_id="d2")
        assert resp.status_code == 200
        assert GradingSession.objects.filter(submission=sub).count() == 2


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


@pytest.mark.django_db
class TestCurrentGradingSessionHelper:
    def test_current_grading_session_returns_non_superseded(self, membership):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="d1")
        sub = Submission.objects.get(pr_number=1)
        iter1 = GradingSession.objects.get(submission=sub)
        iter1.state = GradingSession.State.POSTED
        iter1.save(update_fields=["state"])

        post_webhook(client, make_pr_payload(action="synchronize"), delivery_id="d2")

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

        post_webhook(client, make_pr_payload(action="synchronize"), delivery_id="d2")
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
