"""
GitHub PR comment poster — the concurrency-hardened Send + Resume path.

From the eng-review Section 2 error map and the concurrency bundle:
  - All-or-nothing Send with a per-comment client_mutation_id ledger
  - Each PostedComment row is written in its own short transaction,
    immediately after the GitHub 201 response. The comment loop is NOT
    wrapped in atomic().
  - On failure mid-loop, raise PartialPostError with posted_ids so the
    ViewSet can move the session to PARTIAL state.
  - Resume looks up PostedComment rows and skips anything already posted.
  - Idempotency: client_mutation_id = sha256(session_id | file | line |
    body_hash). Same comment = same id = skipped on retry.

v1.1 auth model — GitHub App (preferred path):
  - When a StudentRepo + GitHubInstallation row exists for the
    submission's repo, mint a short-lived (~1h) installation token via
    users.github_app.mint_installation_token() and use that as the
    bearer credential. Comments post under the LEERA App's identity
    (e.g. "leera[bot] commented") rather than the teacher's account.
    Teachers never need to be repo collaborators.
  - Falls back to the legacy PAT path below if no installation is
    found — keeps tests + transitional deploys working.

Legacy v1 auth (deprecated, kept as fallback):
  - Uses the teacher's encrypted github_personal_access_token (PAT)
    stored on the User model. Required the teacher to be a repo
    collaborator (one invitation per student repo). Replaced by the
    GitHub App migration; this path is left in place so any
    Submissions whose repo predates the App install still work.

v1 limitations noted (to be addressed in v1.1):
  - No OAuth refresh race guard (single PAT per teacher, no expiry).
  - No structured review summary (POST /pulls/{n}/reviews) — we use
    inline comments only. Summary comment is a single top-level comment
    with the rubric scores table.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import transaction

from grading.exceptions import (
    GitHubAuthExpired,
    GitHubError,
    PartialPostError,
    PRClosedError,
)
from grading.models import GradingSession, PostedComment

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────
_GITHUB_TIMEOUT = 20  # seconds per call
_GITHUB_API = "https://api.github.com"


def _github_headers(user_token: str | None) -> dict:
    """Bearer auth with the teacher's PAT; fall back to server GITHUB_TOKEN."""
    token = (user_token or "").strip()
    if not token:
        token = (getattr(settings, "GITHUB_TOKEN", None) or "").strip()
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


from grading.services.github_app_auth import resolve_token_for_repo as _resolve_token


def _parse_repo_full_name(repo_full_name: str) -> tuple[str, str]:
    """'owner/repo' → ('owner', 'repo'). Raises ValueError on bad input."""
    parts = (repo_full_name or "").strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Bad repo_full_name: {repo_full_name!r}")
    return parts[0], parts[1]


# ─────────────────────────────────────────────────────────────────────────────
# PR state fetch
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PRSnapshot:
    state: str          # "open" | "closed"
    merged: bool
    head_sha: str       # the commit we'll attach inline comments to


def _fetch_pr_snapshot(owner: str, repo: str, pr_number: int, token: str | None) -> PRSnapshot:
    """Get the PR's current state + head SHA. Raises PRClosedError if closed."""
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    try:
        r = requests.get(url, headers=_github_headers(token), timeout=_GITHUB_TIMEOUT)
    except requests.RequestException as e:
        raise GitHubError(f"GET /pulls/{pr_number} failed: {e}") from e
    if r.status_code == 401 or r.status_code == 403:
        raise GitHubAuthExpired(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code == 404:
        raise GitHubError(f"PR not found: {owner}/{repo}#{pr_number}")
    if r.status_code != 200:
        raise GitHubError(f"GET /pulls/{pr_number} {r.status_code}: {r.text[:200]}")
    body = r.json()
    if body.get("state") == "closed":
        raise PRClosedError(
            f"PR is closed (merged={body.get('merged')}). Abort send."
        )
    return PRSnapshot(
        state=body.get("state", "open"),
        merged=bool(body.get("merged")),
        head_sha=body.get("head", {}).get("sha", ""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Body formatting — GitHub suggestion syntax
# ─────────────────────────────────────────────────────────────────────────────
def _format_comment_body(
    *,
    body: str,
    teacher_explanation: str = "",
    suggested_snippet: str = "",
) -> str:
    """
    Build the final comment body, optionally appending teacher explanation
    and a GitHub ``` ```suggestion ``` ``` code-fence block.

    Layout when all three are present:

        {body}

        {teacher_explanation}

        ```suggestion
        {suggested_snippet}
        ```

    When suggested_snippet is empty, no fence is appended. When
    teacher_explanation is empty, it is omitted (body and fence are
    separated by a single blank line).

    Newlines + indentation of suggested_snippet are preserved verbatim —
    GitHub's "Commit suggestion" button requires exact whitespace so the
    diff applies cleanly.

    Ref: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/commenting-on-a-pull-request#adding-line-comments-to-a-pull-request
    """
    parts: list[str] = [body or ""]
    explanation = (teacher_explanation or "").strip()
    if explanation:
        parts.append(explanation)
    snippet = suggested_snippet or ""
    if snippet.strip():
        # Preserve exact whitespace inside the fence; strip only a trailing
        # newline so we don't produce a blank final line inside the block.
        snippet_body = snippet.rstrip("\n")
        parts.append(f"```suggestion\n{snippet_body}\n```")
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Comment posting
# ─────────────────────────────────────────────────────────────────────────────
def _post_single_inline_comment(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    token: str | None,
    commit_id: str,
    path: str,
    line: int,
    body: str,
) -> int:
    """
    Post one inline review comment. Returns the GitHub comment id.

    GitHub's POST /pulls/{n}/comments requires:
      body, commit_id, path, line (new line number in the diff hunk), side.
    """
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    payload = {
        "body": body,
        "commit_id": commit_id,
        "path": path,
        "line": line,
        "side": "RIGHT",
    }
    try:
        r = requests.post(
            url,
            headers=_github_headers(token),
            json=payload,
            timeout=_GITHUB_TIMEOUT,
        )
    except requests.RequestException as e:
        raise GitHubError(f"POST comment failed: {e}") from e

    if r.status_code == 401 or r.status_code == 403:
        raise GitHubAuthExpired(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code == 422:
        # Invalid payload (usually path/line doesn't exist in the diff).
        # Don't retry; log and skip this comment — but mark it as GitHubError
        # so the caller treats it as a partial post.
        raise GitHubError(f"422 invalid comment (path={path}, line={line}): {r.text[:200]}")
    if r.status_code >= 500:
        raise GitHubError(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code not in (200, 201):
        raise GitHubError(f"POST unexpected {r.status_code}: {r.text[:200]}")

    return int(r.json().get("id", 0))


def _post_pr_summary_comment(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    token: str | None,
    body: str,
) -> int:
    """
    Post the top-level summary comment (rubric scores table + teacher notes).
    Uses POST /issues/{n}/comments (GitHub treats PRs as issues for top-level comments).
    """
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    try:
        r = requests.post(
            url,
            headers=_github_headers(token),
            json={"body": body},
            timeout=_GITHUB_TIMEOUT,
        )
    except requests.RequestException as e:
        raise GitHubError(f"POST summary comment failed: {e}") from e

    if r.status_code in (401, 403):
        raise GitHubAuthExpired(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code >= 500:
        raise GitHubError(f"GitHub {r.status_code}: {r.text[:200]}")
    if r.status_code not in (200, 201):
        raise GitHubError(f"POST summary {r.status_code}: {r.text[:200]}")
    return int(r.json().get("id", 0))


# ─────────────────────────────────────────────────────────────────────────────
# Summary rendering
# ─────────────────────────────────────────────────────────────────────────────
def _render_summary(session: GradingSession) -> str:
    """
    Build the top-level PR comment from final_scores + rubric + final_summary.
    Markdown table + teacher's custom note.
    """
    rubric = session.rubric
    final_scores = session.final_scores or session.ai_draft_scores or {}
    lines: list[str] = [
        "## Nakijken Copilot — feedback",
        "",
    ]
    if rubric and rubric.criteria:
        lines.append("| Criterion | Score | Evidence |")
        lines.append("|---|---|---|")
        for c in rubric.criteria:
            cid = c.get("id")
            entry = final_scores.get(cid, {}) or {}
            score = entry.get("score", "—")
            evidence = (entry.get("evidence") or "").replace("|", "\\|")
            if len(evidence) > 120:
                evidence = evidence[:117] + "..."
            lines.append(f"| {c.get('name', cid)} | {score} | {evidence} |")
        lines.append("")
    if session.final_summary:
        lines.append(session.final_summary)
        lines.append("")
    lines.append("_Reviewed by your teacher via Nakijken Copilot._")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SendResult:
    posted_count: int
    skipped_duplicate_count: int
    summary_comment_id: int | None


def post_all_or_nothing(
    session: GradingSession,
    *,
    teacher_pat: str | None,
) -> SendResult:
    """
    Post every approved comment to the PR.

    Contract:
      - Caller has already transitioned session.state → SENDING via
        select_for_update in the ViewSet. This function does NOT touch state.
      - On complete success: all comments posted (duplicates skipped),
        summary comment posted, session is ready to be moved to POSTED by caller.
      - On partial failure: raises PartialPostError with posted_ids so far.
        Caller moves session to PARTIAL state and stores partial_post_error.
      - Each PostedComment row is persisted in its OWN short transaction
        immediately after its GitHub 201, per eng-review concurrency bundle.

    Duplicates (PostedComment already exists for the client_mutation_id)
    are silently skipped — this IS the idempotency guarantee.
    """
    submission = session.submission
    owner, repo = _parse_repo_full_name(submission.repo_full_name)
    pr_number = submission.pr_number

    # Resolve the bearer token: prefer the GitHub App installation
    # token (acts as leera[bot] on the repo); fall back to the
    # teacher's PAT during the migration window.
    token = _resolve_token(submission.repo_full_name, teacher_pat)

    snap = _fetch_pr_snapshot(owner, repo, pr_number, token)

    # Source of truth for what to post: final_comments (docent-edited),
    # falling back to ai_draft_comments if docent didn't edit.
    comments_to_post = session.final_comments or session.ai_draft_comments or []

    posted_ids: list[int] = []
    skipped = 0

    for idx, c in enumerate(comments_to_post):
        path = c.get("file") or c.get("path") or ""
        line = int(c.get("line") or 0)
        body = c.get("body") or ""
        teacher_explanation = c.get("teacher_explanation") or ""
        suggested_snippet = c.get("suggested_snippet") or ""

        if not path or line <= 0 or not body.strip():
            log.warning(
                "github_poster: skipping malformed comment idx=%d in session=%s",
                idx, session.id,
            )
            continue

        formatted_body = _format_comment_body(
            body=body,
            teacher_explanation=teacher_explanation,
            suggested_snippet=suggested_snippet,
        )

        # mutation_id is based on the composed body: an edited explanation
        # or snippet means a new comment, so Resume re-posts instead of
        # skipping as a duplicate.
        mutation_id = PostedComment.compute_mutation_id(session.id, path, line, formatted_body)

        # Dupe check (eng-review idempotency guarantee).
        existing = PostedComment.objects.filter(
            grading_session=session, client_mutation_id=mutation_id,
        ).first()
        if existing:
            skipped += 1
            continue

        try:
            gh_id = _post_single_inline_comment(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                token=token,
                commit_id=snap.head_sha,
                path=path,
                line=line,
                body=formatted_body,
            )
        except (GitHubError, GitHubAuthExpired) as e:
            # Partial failure. Raise so the ViewSet sees posted_ids so far.
            log.warning(
                "github_poster: partial failure at idx=%d session=%s: %s",
                idx, session.id, e,
            )
            raise PartialPostError(posted_ids=posted_ids, failed_at=idx, inner=e) from e

        # Short transaction: one PostedComment row per GitHub 201, outside
        # any enclosing atomic(). Key guarantee: if the process crashes AFTER
        # the POST but BEFORE this insert, Resume will re-POST the same
        # client_mutation_id → GitHub creates a duplicate comment (rare, but
        # users can delete one). Acceptable tradeoff for v1; v1.1 can add an
        # outer log-and-reconcile pass.
        with transaction.atomic():
            PostedComment.objects.create(
                grading_session=session,
                client_mutation_id=mutation_id,
                github_comment_id=gh_id,
                file_path=path,
                line_number=line,
                body_preview=formatted_body[:200],
            )
        posted_ids.append(gh_id)

    # Top-level summary comment (rubric + teacher's notes).
    summary_id: int | None = None
    if session.rubric or session.final_summary:
        summary_body = _render_summary(session)
        try:
            summary_id = _post_pr_summary_comment(
                owner=owner, repo=repo, pr_number=pr_number,
                token=token,
                body=summary_body,
            )
        except (GitHubError, GitHubAuthExpired) as e:
            # Inline comments already landed. Treat summary-only failure
            # as partial: the teacher can retry via Resume to re-post just
            # the summary.
            log.warning(
                "github_poster: summary comment failed session=%s: %s",
                session.id, e,
            )
            raise PartialPostError(
                posted_ids=posted_ids,
                failed_at=len(comments_to_post),  # past the inline list
                inner=e,
            ) from e

    return SendResult(
        posted_count=len(posted_ids),
        skipped_duplicate_count=skipped,
        summary_comment_id=summary_id,
    )


def resume_partial(
    session: GradingSession,
    *,
    teacher_pat: str | None,
) -> SendResult:
    """
    Resume a partial send. Thin wrapper around post_all_or_nothing because
    the duplicate-skip logic IS the resume logic — any comments already in
    PostedComment get skipped, everything else gets posted.
    """
    return post_all_or_nothing(session, teacher_pat=teacher_pat)
