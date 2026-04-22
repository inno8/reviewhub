"""
Shared virtual-Project helper used by the grading flow.

Why this exists
---------------
SkillObservation.project and Evaluation.project are both non-nullable FKs to
the legacy projects.Project model. The new Leera grading flow (Cohort /
Course / Submission / GradingSession) has no Project concept — but we need
to satisfy those FKs to write observations and evaluations without making
project nullable (which would ripple through the evaluations/ app).

The pragmatic v1 fix: get_or_create a "virtual" Project per
(repo_owner, repo_name) and reuse it across all grading sessions for that
repo. See grading/services/skill_binding.py for the original rationale.

This module exposes the helper as a standalone function so both
skill_binding and the grading webhook use the exact same logic — we do NOT
want two different "split owner/name" behaviours floating around.
"""
from __future__ import annotations


def get_or_create_virtual_project(submission):
    """
    Return (or create) a legacy projects.Project row standing in for the
    Submission's GitHub repo.

    Matching key: (provider=github, repo_owner, repo_name). The Submission's
    `repo_full_name` ("owner/name") is split to derive owner and name; if
    that field is malformed we fall back to ("unknown", repo_full_name or
    "unknown") so get_or_create still succeeds.
    """
    from projects.models import Project

    repo_full_name = submission.repo_full_name or ""
    if "/" in repo_full_name:
        repo_owner, repo_name = repo_full_name.split("/", 1)
    else:
        repo_owner, repo_name = "unknown", repo_full_name or "unknown"

    project, _created = Project.objects.get_or_create(
        provider=Project.Provider.GITHUB,
        repo_owner=repo_owner,
        repo_name=repo_name,
        defaults={
            "name": repo_full_name or repo_name,
            "created_by": submission.student,
            "repo_url": submission.pr_url or "",
        },
    )
    return project
