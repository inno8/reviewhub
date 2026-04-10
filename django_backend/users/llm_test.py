"""
Minimal LLM connectivity test (admin settings): send a short user message and return reply text.

Uses only the stdlib (urllib) so this works even when httpx is not installed in the venv.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from urllib.parse import urlencode

USER_PROMPT = "How are you? Reply in one short friendly sentence only."


class LLMTestError(Exception):
    """Provider returned an error or unexpected response."""


def _truncate(s: str, max_len: int = 280) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _post_json(
    url: str,
    headers: dict[str, str],
    body: dict,
    timeout: float = 30.0,
) -> tuple[int, object]:
    """POST JSON; returns (status_code, parsed_json_or_dict_with_raw)."""
    payload = json.dumps(body).encode("utf-8")
    hdrs = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"_raw": text}
    except socket.timeout:
        raise LLMTestError(
            "Request timed out. Check your network, firewall, and provider status."
        ) from None
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        raise LLMTestError(f"Connection failed: {reason}") from None


def _error_message(status: int, data: object) -> str:
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict):
            return str(data["error"].get("message", data))[:500]
        if "_raw" in data:
            return str(data["_raw"])[:200]
    return str(data)[:200]


def ping_openai(api_key: str, model: str, timeout: float = 30.0) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": USER_PROMPT}],
        "max_tokens": 80,
        "temperature": 0.3,
    }
    status, data = _post_json(
        url,
        {"Authorization": f"Bearer {api_key}"},
        body,
        timeout=timeout,
    )
    if status == 401:
        raise LLMTestError("Invalid API key or unauthorized (OpenAI).")
    if status >= 400:
        raise LLMTestError(f"OpenAI error ({status}): {_error_message(status, data)}")
    if not isinstance(data, dict):
        raise LLMTestError("Unexpected OpenAI response.")
    try:
        return _truncate(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as e:
        raise LLMTestError(f"Unexpected OpenAI response shape: {e}") from e


def ping_anthropic(api_key: str, model: str, timeout: float = 30.0) -> str:
    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": model,
        "max_tokens": 120,
        "messages": [{"role": "user", "content": USER_PROMPT}],
    }
    status, data = _post_json(
        url,
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        body,
        timeout=timeout,
    )
    if status == 401:
        raise LLMTestError(
            "Invalid API key or unauthorized (Anthropic). "
            "The Messages API only accepts a key from console.anthropic.com (sk-ant-…). "
            "Claude Code / CLI login tokens are not valid here—use Create key in the Console."
        )
    if status >= 400:
        raise LLMTestError(f"Anthropic error ({status}): {_error_message(status, data)}")
    if not isinstance(data, dict):
        raise LLMTestError("Unexpected Anthropic response.")
    try:
        parts = data["content"]
        if not parts:
            raise LLMTestError("Empty response from Anthropic.")
        return _truncate(parts[0].get("text", ""))
    except (KeyError, IndexError, TypeError) as e:
        raise LLMTestError(f"Unexpected Anthropic response shape: {e}") from e


def ping_google_bearer(access_token: str, model: str, timeout: float = 30.0) -> str:
    """Gemini via OAuth (Authorization: Bearer)."""
    mid = model.replace("models/", "").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{mid}:generateContent"
    body = {"contents": [{"parts": [{"text": USER_PROMPT}]}]}
    status, data = _post_json(
        url,
        {"Authorization": f"Bearer {access_token}"},
        body,
        timeout=timeout,
    )
    if status in (401, 403):
        raise LLMTestError("Invalid or expired Google OAuth token.")
    if status >= 400:
        raise LLMTestError(f"Google error ({status}): {_error_message(status, data)}")
    if not isinstance(data, dict):
        raise LLMTestError("Unexpected Gemini response.")
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = parts[0].get("text", "")
        return _truncate(text)
    except (KeyError, IndexError, TypeError) as e:
        raise LLMTestError(f"Unexpected Gemini response shape: {e}") from e


def ping_google(api_key: str, model: str, timeout: float = 30.0) -> str:
    mid = model.replace("models/", "").strip()
    base = f"https://generativelanguage.googleapis.com/v1beta/models/{mid}:generateContent"
    url = f"{base}?{urlencode({'key': api_key})}"
    body = {"contents": [{"parts": [{"text": USER_PROMPT}]}]}
    status, data = _post_json(url, {}, body, timeout=timeout)
    if status in (401, 403):
        raise LLMTestError("Invalid API key or forbidden (Google Gemini).")
    if status >= 400:
        raise LLMTestError(f"Google error ({status}): {_error_message(status, data)}")
    if not isinstance(data, dict):
        raise LLMTestError("Unexpected Gemini response.")
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = parts[0].get("text", "")
        return _truncate(text)
    except (KeyError, IndexError, TypeError) as e:
        raise LLMTestError(f"Unexpected Gemini response shape: {e}") from e


def ping_llm(provider: str, api_key: str, model: str) -> str:
    if not api_key:
        raise LLMTestError("API key is missing.")
    if not (model or "").strip():
        raise LLMTestError("Model is missing.")
    model = model.strip()
    if provider == "openai":
        return ping_openai(api_key, model)
    if provider == "anthropic":
        return ping_anthropic(api_key, model)
    if provider == "google":
        return ping_google(api_key, model)
    raise LLMTestError(f"Unsupported provider: {provider}")


def ping_llm_with_config(cfg) -> str:
    """Run connectivity test using a saved LLMConfiguration row."""
    from .models import LLMConfiguration

    model = (cfg.model or "").strip()
    if not model:
        raise LLMTestError("Model is missing.")

    if cfg.provider == "google":
        if cfg.auth_method == LLMConfiguration.AuthMethod.OAUTH_GOOGLE:
            from .llm_google_oauth import ensure_google_access_token

            access = ensure_google_access_token(cfg)
            return ping_google_bearer(access, model)
        key = cfg.api_key
        if not key:
            raise LLMTestError("API key is missing.")
        return ping_google(key, model)

    secret = cfg.api_key
    if not secret:
        raise LLMTestError("API key or access token is missing.")
    if cfg.provider == "openai":
        return ping_openai(secret, model)
    if cfg.provider == "anthropic":
        return ping_anthropic(secret, model)
    raise LLMTestError(f"Unsupported provider: {cfg.provider}")
