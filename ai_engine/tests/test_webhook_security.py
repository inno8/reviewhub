"""
Tests for webhook security — no secrets in logs, proper signature validation.
"""
import pytest
import hmac
import hashlib
import json
import io
from unittest.mock import patch


# ── P1-2: No secrets leaked in logs ──────────────────────────────────────

def test_no_secrets_in_webhook_source():
    """P1-2: webhooks.py must not contain print statements that leak secrets."""
    import inspect
    from app.api import webhooks

    source = inspect.getsource(webhooks)

    # Must not print the webhook secret
    assert "repr(settings.GITHUB_WEBHOOK_SECRET)" not in source, (
        "webhooks.py still contains debug print of GITHUB_WEBHOOK_SECRET"
    )
    # Must not have debug print statements about signature verification
    assert 'print(f"DEBUG:' not in source, (
        "webhooks.py still contains DEBUG print statements"
    )


def test_no_secrets_in_stdout_during_verification(sample_webhook_payload):
    """P1-2: Webhook processing must not print secrets to stdout."""
    import sys
    from app.api.webhooks import verify_github_signature

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    try:
        secret = "test-secret-value-12345"
        body = json.dumps(sample_webhook_payload).encode()
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        verify_github_signature(body, sig, secret)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    assert "test-secret-value-12345" not in output, (
        "Secret value appeared in stdout during signature verification"
    )
    assert "WEBHOOK_SECRET" not in output, (
        "WEBHOOK_SECRET reference appeared in stdout"
    )


# ── P3-3: GitLab webhook uses correct secret ─────────────────────────────

def test_gitlab_webhook_source_uses_correct_secret():
    """P3-3: GitLab webhook must validate against GITLAB_WEBHOOK_SECRET, not GITHUB."""
    import inspect
    from app.api import webhooks

    source = inspect.getsource(webhooks.gitlab_webhook)

    # The function should NOT reference GITHUB_WEBHOOK_SECRET for validation
    # It should use GITLAB_WEBHOOK_SECRET
    # Note: This checks the source code, not runtime behavior
    lines = source.split("\n")
    for line in lines:
        if "GITHUB_WEBHOOK_SECRET" in line and "x_gitlab_token" in line:
            pytest.fail(
                f"GitLab webhook validates against GITHUB secret: {line.strip()}"
            )
