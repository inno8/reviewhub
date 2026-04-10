"""
List branches for a GitHub repository via the REST API.

User PAT (encrypted on User) is preferred; optional GITHUB_TOKEN in settings is a server fallback.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import requests
from django.conf import settings


def parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    repo_url = (repo_url or "").strip()
    if not repo_url.startswith("https://github.com/"):
        raise ValueError("Only https://github.com/ URLs are supported")
    path = urlparse(repo_url).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError("Could not parse owner/repo from URL")
    return parts[-2], parts[-1]


def _github_headers(user_token: Optional[str] = None) -> dict:
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


def fetch_branch_names(
    owner: str,
    repo: str,
    *,
    user_token: Optional[str] = None,
    timeout: int = 30,
) -> list[str]:
    """Return all branch tip names (paginated)."""
    names: list[str] = []
    url = f"https://api.github.com/repos/{owner}/{repo}/branches"
    headers = _github_headers(user_token)
    while url:
        r = requests.get(url, headers=headers, params={"per_page": 100}, timeout=timeout)
        if r.status_code == 404:
            raise ValueError(
                "Repository not found or not accessible. "
                "For private repositories, add a GitHub token in Settings → Profile."
            )
        r.raise_for_status()
        for item in r.json():
            name = item.get("name")
            if name:
                names.append(name)
        url = None
        link = r.headers.get("Link", "")
        for part in link.split(","):
            if 'rel="next"' in part:
                start = part.find("<") + 1
                end = part.find(">")
                if start > 0 and end > start:
                    url = part[start:end]
                break
    return names


def branches_with_author_activity(
    owner: str,
    repo: str,
    branch_names: list[str],
    author: str,
    *,
    user_token: Optional[str] = None,
    timeout: int = 20,
) -> list[str]:
    """
    Keep branches where at least one commit matches GitHub's ` commits` author filter.
    """
    author = (author or "").strip()
    if not author:
        return list(branch_names)

    headers = _github_headers(user_token)
    out: list[str] = []
    api = f"https://api.github.com/repos/{owner}/{repo}/commits"
    for name in branch_names:
        r = requests.get(
            api,
            headers=headers,
            params={"sha": name, "author": author, "per_page": 1},
            timeout=timeout,
        )
        if r.status_code != 200:
            continue
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            out.append(name)
    return out


def list_active_branches(
    repo_url: str,
    author: Optional[str] = None,
    user_token: Optional[str] = None,
) -> list[str]:
    """
    Branches to offer in the batch UI.
    If author is set, only branches with at least one commit by that author (GitHub API).
    """
    owner, repo = parse_github_owner_repo(repo_url)
    names = fetch_branch_names(owner, repo, user_token=user_token)
    if not names:
        return []
    return branches_with_author_activity(
        owner, repo, names, author or "", user_token=user_token
    )
