"""
GitHub App authentication helpers.

Mints short-lived installation access tokens by:
  1. Signing a JWT with the App's RSA private key (10-min validity)
  2. Exchanging the JWT for an installation token via
     POST /app/installations/<installation_id>/access_tokens
  3. Caching the token in process memory until ~5 min before its
     expiry, then minting a fresh one on next demand

The App private key never leaves Django. ai-engine receives
short-lived installation tokens via Django→ai-engine request payloads
and uses them to clone repos. Webhook signature verification reuses
GITHUB_WEBHOOK_SECRET (same secret across the App's webhook config
and Django's request handler).

Settings consumed:
  GITHUB_APP_ID                  — numeric App ID (e.g. "123456")
  GITHUB_APP_PRIVATE_KEY         — inline PEM content (with \\n escapes), OR
  GITHUB_APP_PRIVATE_KEY_PATH    — path to .pem file inside the container

Env-only — these never touch the DB. Per the architecture doc, only
*per-org* LLM keys live in DB (LLMConfiguration); App-level credentials
are deployment-time secrets.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import jwt
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Configuration loading
# ─────────────────────────────────────────────────────────────────────

class GitHubAppConfigError(Exception):
    """Raised when the App credentials are missing or malformed."""


def _load_private_key() -> bytes:
    """
    Resolve the App's RSA private key, file path first then inline.

    Returns the PEM bytes. Raises GitHubAppConfigError on misconfiguration.
    """
    path = (getattr(settings, 'GITHUB_APP_PRIVATE_KEY_PATH', '') or '').strip()
    if path:
        try:
            with open(path, 'rb') as f:
                content = f.read()
        except OSError as e:
            raise GitHubAppConfigError(
                f'GITHUB_APP_PRIVATE_KEY_PATH={path!r} is not readable: {e}'
            ) from e
        if b'BEGIN' not in content or b'PRIVATE KEY' not in content:
            raise GitHubAppConfigError(
                f'GITHUB_APP_PRIVATE_KEY_PATH file does not look like a PEM key.'
            )
        return content

    inline = getattr(settings, 'GITHUB_APP_PRIVATE_KEY', '') or ''
    if not inline:
        raise GitHubAppConfigError(
            'No GitHub App private key configured. Set either '
            'GITHUB_APP_PRIVATE_KEY (inline PEM with \\n escapes) or '
            'GITHUB_APP_PRIVATE_KEY_PATH (path to .pem inside the container).'
        )

    # Inline PEMs in env files use literal \n escapes for newlines —
    # convert back to actual newlines before handing to PyJWT.
    pem = inline.replace('\\n', '\n').encode()
    if b'BEGIN' not in pem or b'PRIVATE KEY' not in pem:
        raise GitHubAppConfigError(
            'GITHUB_APP_PRIVATE_KEY does not look like a PEM. Make sure '
            'BEGIN/END markers are present and newlines are encoded as '
            'literal \\n (two characters: backslash + n) in .env.'
        )
    return pem


def _app_id() -> str:
    app_id = (getattr(settings, 'GITHUB_APP_ID', '') or '').strip()
    if not app_id:
        raise GitHubAppConfigError(
            'GITHUB_APP_ID is not set. Copy the numeric App ID from your '
            'App settings page on github.com.'
        )
    return app_id


def is_github_app_configured() -> bool:
    """
    Return True iff env has both an App ID and a key, without raising.
    Useful for views that need to render a "Connect GitHub" button only
    when the App is reachable.
    """
    try:
        _app_id()
        _load_private_key()
        return True
    except GitHubAppConfigError:
        return False


# ─────────────────────────────────────────────────────────────────────
# JWT signing — App-level identity (10-min validity)
# ─────────────────────────────────────────────────────────────────────

def _build_app_jwt() -> str:
    """
    Sign a JWT identifying the LEERA App. Used to authenticate
    /app/* endpoints (notably to mint installation tokens). Valid for
    ~10 minutes, the maximum GitHub allows.

    Per GitHub docs: clock-skew tolerance is small, so we use iat -60s
    to absorb minor drift.
    """
    now = int(time.time())
    payload = {
        'iat': now - 60,                  # absorb up to 60s of clock skew
        'exp': now + (9 * 60),            # 9 minutes; <10 min cap
        'iss': _app_id(),                 # GitHub App ID
    }
    return jwt.encode(payload, _load_private_key(), algorithm='RS256')


# ─────────────────────────────────────────────────────────────────────
# Installation tokens (in-process cache)
# ─────────────────────────────────────────────────────────────────────

@dataclass
class _CachedToken:
    token: str
    expires_at: float          # epoch seconds


# {installation_id: _CachedToken}. Per-process cache (each gunicorn
# worker has its own); fine for our scale, would move to Redis in
# multi-host deployments.
_token_cache: dict[int, _CachedToken] = {}
_cache_lock = threading.Lock()

# Margin before expiry — refresh 5 min early so we never hand out a
# token that's about to die mid-request.
_REFRESH_MARGIN_SECONDS = 5 * 60


def mint_installation_token(installation_id: int) -> str:
    """
    Return a valid installation access token for the given installation.

    Caches in process memory until close to expiry. First call costs one
    POST to api.github.com; subsequent calls within ~55 minutes are free.

    Raises:
        GitHubAppConfigError — App ID or private key unset / unreadable.
        requests.HTTPError    — GitHub rejected the JWT (App suspended,
                                installation deleted, etc.).
    """
    now = time.time()
    with _cache_lock:
        cached = _token_cache.get(installation_id)
        if cached and cached.expires_at - now > _REFRESH_MARGIN_SECONDS:
            return cached.token

    # Need a fresh token. Sign a JWT and POST to GitHub.
    app_jwt = _build_app_jwt()
    url = f'https://api.github.com/app/installations/{installation_id}/access_tokens'
    response = requests.post(
        url,
        headers={
            'Authorization': f'Bearer {app_jwt}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        },
        timeout=10,
    )
    if response.status_code == 401:
        raise GitHubAppConfigError(
            f'GitHub rejected the App JWT (401). Common causes: '
            f'wrong GITHUB_APP_ID, malformed private key, or clock skew '
            f'> 60s on the host. Body: {response.text[:200]}'
        )
    if response.status_code == 404:
        raise GitHubAppConfigError(
            f'Installation {installation_id} not found (404). The user '
            f'may have uninstalled the App. Mark the GitHubInstallation '
            f'row deleted_at and prompt re-install.'
        )
    response.raise_for_status()

    body = response.json()
    token = body['token']
    expires_at_iso = body['expires_at']
    # Parse "2026-04-29T11:00:00Z" → epoch float
    from datetime import datetime, timezone
    expires_at_dt = datetime.fromisoformat(expires_at_iso.replace('Z', '+00:00'))
    expires_at = expires_at_dt.replace(tzinfo=timezone.utc).timestamp()

    with _cache_lock:
        _token_cache[installation_id] = _CachedToken(
            token=token,
            expires_at=expires_at,
        )

    logger.info(
        'Minted GitHub installation token for installation_id=%s, '
        'valid for %.0fs',
        installation_id,
        expires_at - now,
    )
    return token


def invalidate_token_cache(installation_id: int | None = None) -> None:
    """
    Drop cached tokens. Useful when handling `installation` webhook
    events for suspend/delete, so the next call mints fresh and gets
    a clean error if the install no longer exists.

    Pass None to clear every cached token (e.g. after rotating the
    App's private key — every existing JWT is now invalid).
    """
    with _cache_lock:
        if installation_id is None:
            _token_cache.clear()
        else:
            _token_cache.pop(installation_id, None)


# ─────────────────────────────────────────────────────────────────────
# Repo listing — what can this installation see?
# ─────────────────────────────────────────────────────────────────────

def list_installation_repos(installation_id: int) -> list[dict]:
    """
    Return the list of repos this installation has access to.

    Used at install-callback time to populate StudentRepo rows, and
    after `installation_repositories` webhook events to refresh the
    set. Each dict is the GitHub Repository payload — useful fields:
      id, full_name, default_branch, private

    Paginates through all results (100/page). Most students have
    1-3 repos so a single page is the common case.
    """
    token = mint_installation_token(installation_id)
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    repos: list[dict] = []
    page = 1
    while True:
        response = requests.get(
            'https://api.github.com/installation/repositories',
            headers=headers,
            params={'per_page': 100, 'page': page},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        page_repos = body.get('repositories', [])
        repos.extend(page_repos)
        if len(page_repos) < 100:
            break
        page += 1
        if page > 50:
            # 5000+ repos is implausible for one install; bail rather
            # than spin. Tighten the App's permissions if you hit this.
            logger.warning(
                'Installation %s has >5000 repos; truncating list',
                installation_id,
            )
            break
    return repos


# ─────────────────────────────────────────────────────────────────────
# Verifying webhook signatures — used by the existing webhook handler
# ─────────────────────────────────────────────────────────────────────

def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verify a GitHub webhook delivery signature.

    `signature_header` is the value of the `X-Hub-Signature-256` header,
    formatted "sha256=<hex>".

    Returns True iff the HMAC-SHA256 of payload_body using
    GITHUB_WEBHOOK_SECRET matches signature_header.
    """
    import hashlib
    import hmac

    secret = (getattr(settings, 'GITHUB_WEBHOOK_SECRET', '') or '').strip()
    if not secret:
        # Mis-configuration — accepting unsigned webhooks would be a
        # security hole. Force operator to set the secret.
        logger.error(
            'GITHUB_WEBHOOK_SECRET is not set; rejecting webhook delivery'
        )
        return False
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    expected = hmac.new(
        secret.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix('sha256=')
    return hmac.compare_digest(expected, received)
