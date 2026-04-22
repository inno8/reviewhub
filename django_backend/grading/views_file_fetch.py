"""
File-content fetch endpoint for the grading inline-comment code modal.

Teachers reviewing an AI-drafted inline comment want to see the file in
context (not just the diff snippet) before accepting/editing/rejecting
the comment. This endpoint proxies GitHub's Contents API using the
requesting user's encrypted PAT (with fallback to the settings-level
GITHUB_TOKEN).

Shape:
    GET /api/grading/sessions/<id>/file/?path=<rel_path>&ref=<sha_or_branch>

Security:
    - Session lookup goes through GradingSession.objects.for_user(user),
      so cross-org returns 404 (not 403) — the existing org-isolation
      contract documented in grading/managers.py.
    - Teachers in the org and the submitting student can read; anyone
      else gets 404.

Graceful degradation:
    - No PAT available at all → 503 with a friendly message. Frontend
      shows a "Add a PAT in settings" panel but keeps the textarea
      functional.
    - GitHub 404 / other upstream errors are surfaced so the frontend
      can show a targeted error.

This lives in its own module to avoid touching `views.py` (currently
WIP on this branch). Registered in `grading/urls.py`.
"""
from __future__ import annotations

from urllib.parse import quote

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GradingSession
from .permissions import _is_admin, _is_teacher_or_admin


# GitHub refuses blobs larger than a few MB via the contents endpoint anyway,
# but we cap before sending to the frontend so the Monaco-less <pre> doesn't
# choke.
MAX_CONTENT_BYTES = 500_000


def _encode_github_path(path: str) -> str:
    """URL-encode each path segment but keep the slashes."""
    path = (path or "").strip().lstrip("/").replace("\\", "/")
    segments = [s for s in path.split("/") if s]
    return "/".join(quote(seg, safe="") for seg in segments)


def _can_access_session(user, session: GradingSession) -> bool:
    """
    Teachers/admins in the session's org, and the submitting student.

    The `for_user()` queryset already filters by org, so by the time we
    get here we know the session is in the user's org (or the user is
    a superuser). This is just the role gate.
    """
    if getattr(user, "is_superuser", False):
        return True
    if _is_teacher_or_admin(user) or _is_admin(user):
        return True
    # Student: only their own submission's files.
    return session.submission.student_id == getattr(user, "id", None)


class GradingSessionFileContentView(APIView):
    """GET /api/grading/sessions/<id>/file/?path=...&ref=..."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        path = (request.query_params.get("path") or "").strip()
        if not path:
            return Response(
                {"detail": "Missing required query parameter: path"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Org-scoped lookup. Cross-org = 404, per the isolation contract.
        base_qs = GradingSession.objects.for_user(request.user).select_related(
            "submission"
        )
        session = get_object_or_404(base_qs, pk=pk)

        if not _can_access_session(request.user, session):
            # Masquerade as 404 to avoid leaking the session's existence
            # to students outside the submission.
            return Response(status=status.HTTP_404_NOT_FOUND)

        submission = session.submission
        repo_full_name = (submission.repo_full_name or "").strip()
        if "/" not in repo_full_name:
            return Response(
                {"detail": "Submission has no valid repo_full_name."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        owner, _, repo = repo_full_name.partition("/")

        ref = (
            (request.query_params.get("ref") or "").strip()
            or (submission.head_branch or "").strip()
            or "main"
        )

        token = (getattr(request.user, "github_personal_access_token", None) or "").strip()
        if not token:
            token = (getattr(settings, "GITHUB_TOKEN", None) or "").strip()
        if not token:
            return Response(
                {
                    "detail": (
                        "Add a GitHub PAT in settings to view code in context."
                    ),
                    "code": "no_pat",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        path_encoded = _encode_github_path(path)
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path_encoded}"
        headers = {
            "Accept": "application/vnd.github.raw",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
        }
        try:
            r = requests.get(url, params={"ref": ref}, headers=headers, timeout=30)
        except requests.RequestException as exc:
            return Response(
                {"detail": f"GitHub fetch failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if r.status_code == 404:
            return Response(
                {"detail": "File not found at that ref."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if r.status_code != 200:
            return Response(
                {
                    "detail": (
                        f"GitHub returned {r.status_code} fetching the file."
                    ),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        raw = r.text or ""
        size = len(raw.encode("utf-8", errors="replace"))
        truncated = False
        if size > MAX_CONTENT_BYTES:
            # Keep the first ~1000 lines — enough context around most
            # inline-comment targets, avoids shipping multi-MB blobs.
            lines = raw.splitlines()
            raw = "\n".join(lines[:1000])
            truncated = True

        return Response(
            {
                "path": path,
                "ref": ref,
                "content": raw,
                "encoding": "utf-8",
                "size": size,
                "truncated": truncated,
            }
        )
