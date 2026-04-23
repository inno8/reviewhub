"""
Tests for Workstream G — shared-repo support (group projects).

Covers:
  * Webhook with N cohort members sharing a repo URL → 1 Submission + N
    SubmissionContributor rows.
  * Primary-author selection rules (PR-author-in-cohort vs alphabetical fallback).
  * Equal-split contribution_fraction when commit-level data is not fetched.
  * contribution_fraction sums to ~1.0.
  * Permission: teacher in cohort A can open sessions where a co-contributor
    from cohort B is attached; teachers not in any contributor's cohort are
    forbidden.
  * Solo-repo regression (1 member → 1 contributor row, is_primary_author=True,
    fraction=1.0).
  * Data migration backfill: every existing Submission gets a primary-author
    contributor row (tested via already-applied 0005 migration state).
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
    SubmissionContributor,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
@pytest.fixture
def shared_repo_setup(db):
    """
    Three students (Alice, Bob, Charlie) all sharing the SAME repo URL
    for their group project, all in one cohort, one course.
    """
    from users.models import GitProviderConnection, Organization

    org = Organization.objects.create(name="Media College", slug="media-college-g")
    teacher = User.objects.create_user(
        username="teacher_g", email="teacher_g@ex.com", password="pw",
        role="teacher", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="GroupRubric",
        criteria=[
            {"id": "readability", "name": "Readability", "weight": 1,
             "levels": [{"score": 1}, {"score": 4}]}
        ],
    )
    cohort = Cohort.objects.create(org=org, name="MBO-4 ICT Group")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Frontend", rubric=rubric,
    )

    repo_url = "https://github.com/team-alpha/groupwork-q3"
    students = []
    for username, email in [
        ("alice_g", "alice@ex.com"),
        ("bob_g", "bob@ex.com"),
        ("charlie_g", "charlie@ex.com"),
    ]:
        u = User.objects.create_user(
            username=username, email=email, password="pw",
            role="developer", organization=org,
        )
        GitProviderConnection.objects.create(
            user=u, provider="github", username=username,
        )
        CohortMembership.objects.create(
            cohort=cohort, student=u, student_repo_url=repo_url,
        )
        students.append(u)

    return {
        "org": org,
        "teacher": teacher,
        "cohort": cohort,
        "course": course,
        "students": students,
        "repo_url": repo_url,
    }


def make_pr_payload(
    *, author: str = "alice_g", pr_number: int = 1,
    repo_full_name: str = "team-alpha/groupwork-q3",
    action: str = "opened",
):
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "state": "open",
            "merged": False,
            "title": "Add feature",
            "html_url": f"https://github.com/{repo_full_name}/pull/{pr_number}",
            "head": {"ref": "feat/foo", "sha": "sha1"},
            "base": {"ref": "main"},
            "user": {"login": author},
        },
        "repository": {
            "full_name": repo_full_name,
            "html_url": f"https://github.com/{repo_full_name}",
        },
    }


def post_webhook(client, payload, *, delivery_id="g-d1"):
    body = json.dumps(payload).encode()
    return client.post(
        "/api/grading/webhooks/github/",
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_DELIVERY=delivery_id,
        HTTP_X_GITHUB_EVENT="pull_request",
    )


# ─────────────────────────────────────────────────────────────────────
# Webhook: shared repo → multi-contributor Submission
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSharedRepoWebhook:
    def test_three_members_one_submission_three_contributors(self, shared_repo_setup):
        client = APIClient()
        resp = post_webhook(client, make_pr_payload(author="alice_g"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["contributor_count"] == 3
        assert set(data["contributors"]) == {"alice@ex.com", "bob@ex.com", "charlie@ex.com"}

        assert Submission.objects.count() == 1
        sub = Submission.objects.get()
        links = sub.contributor_links.all()
        assert links.count() == 3

    def test_primary_is_pr_author_when_author_matches_contributor(self, shared_repo_setup):
        client = APIClient()
        post_webhook(client, make_pr_payload(author="bob_g"))
        sub = Submission.objects.get()
        primaries = sub.contributor_links.filter(is_primary_author=True)
        assert primaries.count() == 1
        assert primaries.first().user.email == "bob@ex.com"
        # Submission.student mirrors the primary for convenience.
        assert sub.student.email == "bob@ex.com"

    def test_primary_falls_back_to_alphabetical_when_author_unknown(
        self, shared_repo_setup
    ):
        """If PR author's GitHub login doesn't map to any contributor, primary
        is the first contributor sorted alphabetically by email."""
        client = APIClient()
        # "random-user" has no GitProviderConnection
        post_webhook(client, make_pr_payload(author="random-user"))
        sub = Submission.objects.get()
        primary = sub.contributor_links.get(is_primary_author=True)
        # alphabetical: alice@ex.com < bob@ex.com < charlie@ex.com
        assert primary.user.email == "alice@ex.com"

    def test_equal_split_contribution_fractions(self, shared_repo_setup):
        client = APIClient()
        post_webhook(client, make_pr_payload(author="alice_g"))
        sub = Submission.objects.get()
        links = list(sub.contributor_links.all())
        assert len(links) == 3
        for link in links:
            assert abs(link.contribution_fraction - (1 / 3)) < 1e-4

    def test_fractions_sum_to_approximately_one(self, shared_repo_setup):
        client = APIClient()
        post_webhook(client, make_pr_payload(author="alice_g"))
        sub = Submission.objects.get()
        total = sum(
            link.contribution_fraction for link in sub.contributor_links.all()
        )
        assert abs(total - 1.0) < 1e-3

    def test_synchronize_does_not_duplicate_contributors(self, shared_repo_setup):
        client = APIClient()
        post_webhook(client, make_pr_payload(action="opened"), delivery_id="g-d1")
        post_webhook(
            client,
            make_pr_payload(action="synchronize"),
            delivery_id="g-d2",
        )
        sub = Submission.objects.get()
        assert sub.contributor_links.count() == 3  # unchanged

    def test_exactly_one_submission_for_shared_repo(self, shared_repo_setup):
        """Sanity: 3 memberships, 1 repo_url, 1 PR → exactly 1 Submission
        (not one per contributor)."""
        client = APIClient()
        post_webhook(client, make_pr_payload(author="alice_g"))
        assert Submission.objects.count() == 1
        assert GradingSession.objects.count() == 1


# ─────────────────────────────────────────────────────────────────────
# Regression: solo repo still works
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSoloRepoRegression:
    def test_solo_repo_creates_one_primary_contributor(self, db):
        from users.models import GitProviderConnection, Organization

        org = Organization.objects.create(name="Solo Org", slug="solo-g")
        teacher = User.objects.create_user(
            username="solo_teacher", email="st@ex.com", password="pw",
            role="teacher", organization=org,
        )
        student = User.objects.create_user(
            username="jandeboer_g", email="jan_g@ex.com", password="pw",
            role="developer", organization=org,
        )
        GitProviderConnection.objects.create(
            user=student, provider="github", username="jandeboer_g",
        )
        rubric = Rubric.objects.create(
            org=org, owner=teacher, name="Solo",
            criteria=[{"id": "r", "name": "R", "weight": 1,
                       "levels": [{"score": 1}, {"score": 4}]}],
        )
        cohort = Cohort.objects.create(org=org, name="Solo cohort")
        Course.objects.create(org=org, cohort=cohort, owner=teacher, name="Solo C", rubric=rubric)
        CohortMembership.objects.create(
            cohort=cohort, student=student,
            student_repo_url="https://github.com/jandeboer_g/assignment",
        )

        client = APIClient()
        resp = post_webhook(
            client,
            make_pr_payload(author="jandeboer_g", repo_full_name="jandeboer_g/assignment"),
            delivery_id="solo-d1",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["contributor_count"] == 1

        sub = Submission.objects.get()
        links = sub.contributor_links.all()
        assert links.count() == 1
        link = links.first()
        assert link.is_primary_author is True
        assert abs(link.contribution_fraction - 1.0) < 1e-6
        assert link.user.email == "jan_g@ex.com"


# ─────────────────────────────────────────────────────────────────────
# Data migration backfill
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestMigrationBackfill:
    def test_backfill_creates_primary_contributor_for_prior_submissions(
        self, shared_repo_setup
    ):
        """
        Regression for migration 0005's RunPython. The migration has already
        executed on the test DB; we simulate a pre-migration state by creating
        a Submission and deleting its contributor rows, then verify that
        running the backfill function idempotently re-creates the primary row.
        """
        import importlib
        # Migration module names start with digits; importlib handles that.
        mod = importlib.import_module(
            "grading.migrations.0005_shared_repo_contributors"
        )

        student = shared_repo_setup["students"][0]
        sub = Submission.objects.create(
            org=shared_repo_setup["org"],
            course=shared_repo_setup["course"],
            student=student,
            repo_full_name="team-alpha/legacy-repo",
            pr_number=99,
            pr_url="https://github.com/team-alpha/legacy-repo/pull/99",
            head_branch="legacy",
        )
        # Delete any auto-created contributor rows
        sub.contributor_links.all().delete()
        assert sub.contributor_links.count() == 0

        # Simulate the backfill using a tiny apps shim
        class _Apps:
            def get_model(self, app, model):
                from django.apps import apps as django_apps
                return django_apps.get_model(app, model)
        mod.backfill_primary_contributors(_Apps(), None)

        links = sub.contributor_links.all()
        assert links.count() == 1
        assert links.first().is_primary_author is True
        assert abs(links.first().contribution_fraction - 1.0) < 1e-6


# ─────────────────────────────────────────────────────────────────────
# Permissions — teacher of any contributor's cohort can access
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSharedRepoPermissions:
    def test_teacher_in_contributor_cohort_can_view_session(self, shared_repo_setup):
        client = APIClient()
        post_webhook(client, make_pr_payload(author="alice_g"))
        session = GradingSession.objects.get()
        teacher = shared_repo_setup["teacher"]

        auth_client = APIClient()
        auth_client.force_authenticate(user=teacher)
        resp = auth_client.get(f"/api/grading/sessions/{session.id}/")
        assert resp.status_code == 200, resp.content
        # Contributors exposed in detail serializer.
        body = resp.json()
        contrib_emails = {c["user_email"] for c in body.get("contributors", [])}
        assert contrib_emails == {
            "alice@ex.com", "bob@ex.com", "charlie@ex.com",
        }

    def test_teacher_outside_all_cohorts_gets_403_or_404(self, shared_repo_setup):
        """A teacher whose courses are not in any contributor's cohort cannot
        view the session. DRF permissions typically return 403 or 404 —
        accept either as long as it's a denial."""
        from users.models import Organization

        client = APIClient()
        post_webhook(client, make_pr_payload(author="alice_g"))
        session = GradingSession.objects.get()

        other_org = Organization.objects.create(name="Other Org", slug="other-g")
        outsider = User.objects.create_user(
            username="outsider_g", email="out@ex.com", password="pw",
            role="teacher", organization=other_org,
        )
        auth_client = APIClient()
        auth_client.force_authenticate(user=outsider)
        resp = auth_client.get(f"/api/grading/sessions/{session.id}/")
        assert resp.status_code in (403, 404), resp.status_code


# ─────────────────────────────────────────────────────────────────────
# No-match path still returns 200 matched=false
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestNoMatchPath:
    def test_no_membership_match_returns_unmatched(self, shared_repo_setup):
        client = APIClient()
        resp = post_webhook(
            client,
            make_pr_payload(
                author="noone",
                repo_full_name="some-stranger/unknown-repo",
            ),
        )
        assert resp.status_code == 200
        assert resp.json()["matched"] is False
        assert Submission.objects.count() == 0
