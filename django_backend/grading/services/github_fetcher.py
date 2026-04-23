"""
On-demand GitHub fetcher for PR metadata + diffs.

Used by:
  - grading.views.GradingSessionViewSet.generate_draft — fetches the live
    PR diff at grade-time so the teacher always sees the current state
    (not a stale snapshot from a push webhook hours ago).
  - grading.webhooks (the PR webhook handler) — verifies the PR still
    exists and pulls the head commit SHA when creating a Submission.

v1 auth: uses the teacher's encrypted github_personal_access_token (PAT)
stored on the User model. Falls back to settings.GITHUB_TOKEN for server-
side calls (webhook handler doesn't have a user context).

Why fetch the diff fresh instead of reusing push-webhook Evaluations:
  - Student pushes a commit → ai_engine fires a per-commit Evaluation.
    That's the student-facing learning loop (continuous feedback on every
    commit).
  - Teacher opens PR to grade → the "right" diff is the PR's aggregate
    changes (base...head), NOT a concatenation of per-commit diffs.
    GitHub's pull/{n}/files endpoint returns exactly that.
  - Decouples grading from the push-evaluation chain entirely.
    GradingSession works even if no Evaluations ever ran.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings

from grading.exceptions import GitHubAuthExpired, GitHubError, PRClosedError

log = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_GITHUB_TIMEOUT = 20


def _github_headers(user_token: Optional[str] = None, accept_diff: bool = False) -> dict:
    token = (user_token or "").strip()
    if not token:
        token = (getattr(settings, "GITHUB_TOKEN", None) or "").strip()
    headers = {
        "Accept": "application/vnd.github.v3.diff" if accept_diff else "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass
class PRInfo:
    owner: str
    repo: str
    pr_number: int
    title: str
    state: str  # "open" | "closed"
    merged: bool
    head_sha: str
    head_ref: str  # branch name
    base_ref: str
    author_login: str
    html_url: str


def fetch_pr_info(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    token: Optional[str] = None,
) -> PRInfo:
    """
    GET /repos/{owner}/{repo}/pulls/{pr_number}.
    Raises PRClosedError if the PR has been merged or closed.
    """
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    try:
        r = requests.get(url, headers=_github_headers(token), timeout=_GITHUB_TIMEOUT)
    except requests.RequestException as e:
        raise GitHubError(f"GET /pulls/{pr_number} failed: {e}") from e

    if r.status_code in (401, 403):
        raise GitHubAuthExpired(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code == 404:
        raise GitHubError(f"PR not found: {owner}/{repo}#{pr_number}")
    if r.status_code != 200:
        raise GitHubError(f"GET /pulls/{pr_number} {r.status_code}: {r.text[:200]}")

    body = r.json()
    if body.get("state") == "closed":
        raise PRClosedError(f"PR #{pr_number} is closed (merged={body.get('merged')})")

    return PRInfo(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        title=body.get("title", ""),
        state=body.get("state", "open"),
        merged=bool(body.get("merged")),
        head_sha=body.get("head", {}).get("sha", ""),
        head_ref=body.get("head", {}).get("ref", ""),
        base_ref=body.get("base", {}).get("ref", "main"),
        author_login=body.get("user", {}).get("login", ""),
        html_url=body.get("html_url", ""),
    )


def fetch_pr_diff(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    token: Optional[str] = None,
) -> str:
    """
    GET /repos/{owner}/{repo}/pulls/{pr_number} with Accept: diff.
    Returns the full unified diff across all commits in the PR.
    """
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    try:
        r = requests.get(
            url,
            headers=_github_headers(token, accept_diff=True),
            timeout=_GITHUB_TIMEOUT,
        )
    except requests.RequestException as e:
        raise GitHubError(f"GET /pulls/{pr_number}.diff failed: {e}") from e

    if r.status_code in (401, 403):
        raise GitHubAuthExpired(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code == 404:
        raise GitHubError(f"PR not found: {owner}/{repo}#{pr_number}")
    if r.status_code != 200:
        raise GitHubError(f"GET /pulls/{pr_number}.diff {r.status_code}: {r.text[:200]}")

    return r.text
