"""
Google OAuth 2.0 for Gemini (LLM settings).

Requires env:
  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  BACKEND_PUBLIC_URL — e.g. https://api.example.com (no trailing slash)

Register this redirect URI in Google Cloud Console (OAuth client, Web application):
  {BACKEND_PUBLIC_URL}/api/users/me/llm-config/oauth/google/callback/

Scopes: Gemini API access via OAuth (see https://ai.google.dev/gemini-api/docs/oauth).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

# Read-only access to Gemini / Generative Language API via user credentials
GOOGLE_OAUTH_SCOPE = "https://www.googleapis.com/auth/generative-language.retriever"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _configured() -> bool:
    return bool(
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        and getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    )


def google_redirect_uri() -> str:
    base = getattr(settings, "BACKEND_PUBLIC_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/api/users/me/llm-config/oauth/google/callback/"


def build_authorization_url(state: str) -> str:
    if not _configured():
        raise RuntimeError("Google OAuth is not configured (missing client id/secret).")
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Return token JSON: access_token, expires_in, refresh_token (first grant), ..."""
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"Google token exchange failed ({e.code}): {body[:500]}") from e


def refresh_access_token(refresh_token: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"Google token refresh failed ({e.code}): {body[:500]}") from e


def apply_initial_oauth_tokens(cfg, token_json: dict) -> None:
    """Persist first token response after authorization code exchange."""
    from datetime import timedelta

    from django.utils import timezone

    cfg.oauth_access_token = token_json["access_token"]
    if token_json.get("refresh_token"):
        cfg.oauth_refresh_token = token_json["refresh_token"]
    exp = token_json.get("expires_in")
    if exp:
        cfg.oauth_expires_at = timezone.now() + timedelta(
            seconds=max(0, int(exp) - 60)
        )
    else:
        cfg.oauth_expires_at = None


def ensure_google_access_token(cfg) -> str:
    """Return a valid Gemini OAuth access token, refreshing and saving cfg when needed."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import LLMConfiguration

    if cfg.auth_method != LLMConfiguration.AuthMethod.OAUTH_GOOGLE:
        raise ValueError("Configuration is not Google OAuth")
    now = timezone.now()
    if (
        cfg.oauth_access_token
        and cfg.oauth_expires_at
        and cfg.oauth_expires_at > now
    ):
        return cfg.oauth_access_token
    rt = cfg.oauth_refresh_token
    if not rt:
        raise RuntimeError(
            "Google OAuth is not connected or the refresh token was revoked. "
            "Sign in with Google again in LLM settings."
        )
    data = refresh_access_token(rt)
    cfg.oauth_access_token = data["access_token"]
    exp = data.get("expires_in")
    if exp:
        cfg.oauth_expires_at = now + timedelta(seconds=max(0, int(exp) - 60))
    cfg.save(
        update_fields=["_oauth_access_token", "oauth_expires_at", "updated_at"]
    )
    return cfg.oauth_access_token
