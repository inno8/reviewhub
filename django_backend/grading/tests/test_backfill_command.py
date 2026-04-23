"""
Tests for the `backfill_student_history` management command (Workstream H).

All GitHub API calls are mocked via `unittest.mock.patch` on `requests.get`.
No network calls in the test suite.
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone as dt_tz
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from evaluations.models import DeterministicFinding, Evaluation
from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    GradingSession,
    Rubric,
    Submission,
    SubmissionContributor,
)
from grading.services import github_backfill

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
def _seed_env(email="jan@example.com"):
    from users.models import Organization
    org = Organization.objects.create(name="Media College", slug="media-col")
    teacher = User.objects.create_user(
        username="docent", email="d@x.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="jan", email=email, password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{"id": "r", "name": "R", "weight": 1,
                   "levels": [{"score": 1}, {"score": 4}]}],
    )
    cohort = Cohort.objects.create(org=org, name="Klas 2A")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Backend", rubric=rubric,
    )
    CohortMembership.objects.create(cohort=cohort, student=student)
    return {"org": org, "teacher": teacher, "student": student,
            "rubric": rubric, "cohort": cohort, "course": course}


def _seed_skill(slug="clean_code"):
    from skills.models import Skill, SkillCategory
    cat, _ = SkillCategory.objects.get_or_create(
        slug="codeq_bh", defaults={"name": "CQ BH", "order": 0},
    )
    skill, _ = Skill.objects.get_or_create(
        slug=slug, defaults={"category": cat, "name": slug, "order": 0},
    )
    return skill


# ─────────────────────────────────────────────────────────────────────
# Fake GitHub API
# ─────────────────────────────────────────────────────────────────────
def _make_pr(number: int, *, merged_days_ago: int, title: str = "feat: x") -> dict:
    ts = (datetime.now(dt_tz.utc) - timedelta(days=merged_days_ago)).isoformat()
    ts = ts.replace("+00:00", "Z")
    return {
        "number": number,
        "title": title,
        "html_url": f"https://github.com/acme/repo/pull/{number}",
        "state": "closed",
        "merged_at": ts,
        "closed_at": ts,
        "updated_at": ts,
        "commits": 3,
        "head": {"ref": f"feat-{number}", "sha": f"sha{number}" + "0" * 36},
        "base": {"ref": "main"},
        "user": {"login": "someone-else"},
    }


_PATCH_WITH_ISSUES = (
    "@@ -0,0 +1,5 @@\n"
    "+# TODO: fix me later\n"
    "+def f():\n"
    "+    try:\n"
    "+        x = 1\n"
    "+    except:\n"
)


def _make_files(with_findings: bool = True) -> list[dict]:
    return [{
        "filename": "app/main.py",
        "additions": 5 if with_findings else 2,
        "deletions": 1,
        "patch": _PATCH_WITH_ISSUES if with_findings else "@@ -0,0 +1,2 @@\n+ok\n+fine\n",
    }]


class _FakeResp:
    def __init__(self, data, status=200, link=None):
        self._data = data
        self.status_code = status
        self.text = ""
        self.headers = {"Link": link or ""}

    def json(self):
        return self._data


def _mock_get_factory(prs, files_by_pr, *, fail_404=False):
    """Build a side-effect function for requests.get."""
    def side_effect(url, **_kw):
        if fail_404 and "/pulls" in url and "/files" not in url:
            return _FakeResp({"message": "Not Found"}, status=404)
        if url.endswith("/pulls") or ("/pulls?" in url and "/files" not in url):
            return _FakeResp(prs)
        if "/files" in url:
            # Extract PR number from URL: .../pulls/<num>/files
            num = int(url.split("/pulls/")[1].split("/")[0])
            return _FakeResp(files_by_pr.get(num, []))
        return _FakeResp([], status=404)
    return side_effect


@pytest.fixture
def gh_token(monkeypatch):
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_test")


# ─────────────────────────────────────────────────────────────────────
# 1. Happy path
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_happy_path_creates_all_rows(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")
    _seed_skill("error_handling")

    prs = [_make_pr(i, merged_days_ago=(i * 5) + 1) for i in (1, 2, 3)]
    files = {i: _make_files(with_findings=True) for i in (1, 2, 3)}

    out = io.StringIO()
    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory(prs, files)):
        call_command(
            "backfill_student_history",
            f"--repo=acme/repo",
            f"--user={env['student'].id}",
            f"--cohort={env['cohort'].id}",
            "--days=90",
            stdout=out,
        )

    assert Submission.objects.count() == 3
    assert GradingSession.objects.count() == 3
    # All sessions are POSTED
    assert all(s.state == GradingSession.State.POSTED
               for s in GradingSession.objects.all())
    # Each PR produced findings (TODO + bare-except at minimum)
    assert DeterministicFinding.objects.count() >= 6
    # Evaluations created
    assert Evaluation.objects.filter(author=env["student"]).count() == 3
    # Contributors attached
    assert SubmissionContributor.objects.filter(
        user=env["student"], is_primary_author=True
    ).count() == 3
    out_text = out.getvalue()
    assert "findings" in out_text
    assert "processed=3" in out_text


# ─────────────────────────────────────────────────────────────────────
# 2. Idempotency
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_idempotent_rerun_creates_no_new_rows(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")
    prs = [_make_pr(1, merged_days_ago=2)]
    files = {1: _make_files()}

    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory(prs, files)):
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     stdout=io.StringIO())
        first_sub_count = Submission.objects.count()
        first_obs_count = Evaluation.objects.count()
        first_find_count = DeterministicFinding.objects.count()

        # Second run — same data
        out2 = io.StringIO()
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     stdout=out2)

    assert Submission.objects.count() == first_sub_count
    assert Evaluation.objects.count() == first_obs_count
    assert DeterministicFinding.objects.count() == first_find_count
    assert "skipped=1" in out2.getvalue()


# ─────────────────────────────────────────────────────────────────────
# 3. Date preservation
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_historical_timestamps_preserved(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")

    target = datetime.now(dt_tz.utc) - timedelta(days=60)
    pr = _make_pr(42, merged_days_ago=60)
    prs = [pr]
    files = {42: _make_files()}

    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory(prs, files)):
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     stdout=io.StringIO())

    sub = Submission.objects.get()
    session = GradingSession.objects.get()
    ev = Evaluation.objects.get()
    finding = DeterministicFinding.objects.first()

    # Each should be ~60 days ago (within 2 days of tolerance),
    # NOT today.
    now = datetime.now(dt_tz.utc)
    for ts in (sub.created_at, session.posted_at, ev.created_at,
               finding.created_at):
        delta_days = (now - ts).days
        assert 58 <= delta_days <= 62, (
            f"timestamp {ts} is {delta_days} days ago, expected ~60"
        )

    # SkillObservation created_at also historical
    from skills.models import SkillObservation
    obs = SkillObservation.objects.first()
    assert obs is not None
    assert 58 <= (now - obs.created_at).days <= 62


# ─────────────────────────────────────────────────────────────────────
# 4. Flexible user attribution
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_user_attribution_overrides_github_author(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")
    pr = _make_pr(1, merged_days_ago=5)
    pr["user"] = {"login": "totally-different-user"}
    prs = [pr]
    files = {1: _make_files()}

    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory(prs, files)):
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     stdout=io.StringIO())

    sub = Submission.objects.get()
    assert sub.student_id == env["student"].id
    contrib = SubmissionContributor.objects.get()
    assert contrib.user_id == env["student"].id
    assert contrib.is_primary_author is True
    assert contrib.contribution_fraction == 1.0


# ─────────────────────────────────────────────────────────────────────
# 5. Dry run
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_dry_run_writes_nothing(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")
    prs = [_make_pr(i, merged_days_ago=i * 3) for i in (1, 2)]
    files = {i: _make_files() for i in (1, 2)}

    out = io.StringIO()
    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory(prs, files)):
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     "--dry-run", stdout=out)

    assert Submission.objects.count() == 0
    assert GradingSession.objects.count() == 0
    assert DeterministicFinding.objects.count() == 0
    assert Evaluation.objects.count() == 0
    assert "would create" in out.getvalue()


# ─────────────────────────────────────────────────────────────────────
# 6. GitHub 404 repo — clear error, no partial writes
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_repo_not_found_fails_cleanly(gh_token):
    env = _seed_env()

    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory([], {}, fail_404=True)):
        with pytest.raises(CommandError) as exc:
            call_command("backfill_student_history", "--repo=acme/missing",
                         f"--user={env['student'].id}",
                         f"--cohort={env['cohort'].id}",
                         stdout=io.StringIO())

    assert "not found" in str(exc.value).lower()
    assert Submission.objects.count() == 0


# ─────────────────────────────────────────────────────────────────────
# 7. No LLM calls
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_no_llm_calls_during_backfill(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")
    prs = [_make_pr(1, merged_days_ago=10)]
    files = {1: _make_files()}

    # Track any outbound HTTP to anything other than api.github.com.
    # No LLM client should be invoked during backfill.
    non_github_calls = []

    real_get = github_backfill.requests.get
    gh_side = _mock_get_factory(prs, files)

    def tracking_get(url, *a, **kw):
        if "api.github.com" not in url:
            non_github_calls.append(url)
        return gh_side(url, *a, **kw)

    # Also assert rubric_grader / LLM adapter helpers are never imported
    # into scope during the run — we patch the module-level requests.get.
    with patch("grading.services.github_backfill.requests.get",
               side_effect=tracking_get):
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     stdout=io.StringIO())

    assert non_github_calls == []
    # Evaluation should have no llm_model set (backfill writes "")
    ev = Evaluation.objects.get()
    assert ev.llm_model == ""
    # And no LLMCostLog rows were written
    from grading.models import LLMCostLog
    assert LLMCostLog.objects.count() == 0


# ─────────────────────────────────────────────────────────────────────
# 8. DeterministicFindings created with correct fields
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_deterministic_findings_have_runner_and_rule(gh_token):
    env = _seed_env()
    _seed_skill("clean_code")
    _seed_skill("error_handling")
    prs = [_make_pr(1, merged_days_ago=3)]
    files = {1: _make_files(with_findings=True)}

    with patch("grading.services.github_backfill.requests.get",
               side_effect=_mock_get_factory(prs, files)):
        call_command("backfill_student_history", "--repo=acme/repo",
                     f"--user={env['student'].id}",
                     f"--cohort={env['cohort'].id}",
                     stdout=io.StringIO())

    findings = DeterministicFinding.objects.all()
    assert findings.count() >= 2
    runners = {f.runner for f in findings}
    assert runners <= {"ruff", "eslint"}  # ruff for .py
    assert "ruff" in runners
    rule_ids = {f.rule_id for f in findings}
    # From the patch: TODO -> T001, bare-except -> E722
    assert "T001" in rule_ids
    assert "E722" in rule_ids
