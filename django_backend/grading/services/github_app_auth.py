"""
Shared GitHub-App-vs-PAT token resolver, used by both
github_poster.py (writes) and github_fetcher.py (reads).

Why a separate module:
  Keeps the resolution logic DRY and lets the rest of the codebase
  use it without each module re-implementing the lookup.

Resolution order:
  1. GitHub App installation token (preferred). If a StudentRepo +
     GitHubInstallation row exists for the given repo, mint a fresh
     short-lived (~1h) installation token via
     users.github_app.mint_installation_token(). Comments, reviews,
     and clones run under the LEERA App's identity.

  2. Legacy teacher PAT (fallback). The caller can pass a teacher's
     personal access token; used during the transition window where
     some Submissions predate the App install. After the migration
     completes this fallback is mostly dead code, kept around for
     tests + crash-safety if the App credentials are temporarily
     misconfigured.

  3. None. No installation, no PAT — caller will likely get 401
     from GitHub. The error path is the right place to surface this
     to the user ("connect GitHub in Settings").
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def resolve_token_for_repo(
    repo_full_name: str,
    fallback_pat: str | None = None,
) -> str | None:
    """
    Return a bearer token for the given repo, preferring App over PAT.

    Args:
        repo_full_name: "owner/repo" format. Used to look up StudentRepo.
        fallback_pat: legacy teacher PAT, used only when no App install
            covers the repo. Empty string and None both treated as
            "no fallback."

    Returns:
        Bearer token string ready for "Authorization: Bearer <token>",
        or None if neither path produces one.
    """
    # Lazy-import to keep webhook test isolation: importing user models
    # at top of module breaks tests that mock django setup partially.
    try:
        from users.models import StudentRepo
        from users.github_app import (
            GitHubAppConfigError,
            mint_installation_token,
        )
    except Exception:
        return (fallback_pat or "").strip() or None

    repo = (
        StudentRepo.objects
        .filter(full_name=repo_full_name, is_active=True)
        .select_related('installation')
        .first()
    )
    if repo and repo.installation and repo.installation.is_active:
        try:
            return mint_installation_token(repo.installation.installation_id)
        except GitHubAppConfigError as e:
            log.warning(
                'GitHub App token mint failed for %s; falling back to PAT: %s',
                repo_full_name, e,
            )
        except Exception:
            log.exception(
                'Unexpected error minting App token for %s; falling back to PAT',
                repo_full_name,
            )

    return (fallback_pat or "").strip() or None
