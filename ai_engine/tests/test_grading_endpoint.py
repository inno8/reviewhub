"""
Tests for the /api/v1/grade rubric-aware grading endpoint.

Focus: the May 7 hero feature — per-comment `original_snippet` +
`suggested_snippet` in the LLM response. These fields drive the inline
three-panel editor in the session detail UI and the GitHub ```suggestion```
block that gives students a one-click "Commit suggestion" button.

Mocks LLMAdapter.call_raw so tests don't hit a real provider.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api.grading import _build_user_prompt, _parse_grade_json, GradeRequest, RubricSpec


client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _base_payload() -> dict:
    return {
        "redacted_diff": (
            "--- a/vault_cli/auth.py\n"
            "+++ b/vault_cli/auth.py\n"
            "@@ -10,0 +10,2 @@\n"
            '+ADMIN_PASSWORD = "admin123"  # tijdelijk wachtwoord\n'
        ),
        "rubric": {
            "criteria": [
                {
                    "id": "security",
                    "name": "Security",
                    "weight": 1.0,
                    "levels": [
                        {"score": 1, "description": "Unsafe"},
                        {"score": 2, "description": "Basic"},
                        {"score": 3, "description": "Solid"},
                    ],
                }
            ],
            "calibration": {"tone": "formal", "language": "en", "depth": "detailed"},
        },
        "context": {},
        "tier": "premium",
        "docent_id": 1,
        # Avoid env-var lookup — the adapter is mocked but its __init__ runs.
        "llm_api_key": "sk-fake-test-key",
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-5",
    }


def _mock_llm_json(comments: list[dict]) -> str:
    return json.dumps(
        {
            "scores": {
                "security": {
                    "score": 1,
                    "evidence": 'ADMIN_PASSWORD = "admin123"',
                }
            },
            "comments": comments,
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Prompt extension: instructions + schema + few-shot examples
# ─────────────────────────────────────────────────────────────────────────────

def test_prompt_requests_original_and_suggested_snippets():
    """The user prompt must ask the LLM for the two new fields."""
    req = GradeRequest(
        redacted_diff="diff",
        rubric=RubricSpec(criteria=[], calibration={}),
    )
    prompt = _build_user_prompt(req)

    # Schema fields present
    assert '"original_snippet"' in prompt
    assert '"suggested_snippet"' in prompt

    # Rules present
    assert "verbatim" in prompt.lower()
    assert "≤10 lines" in prompt or "10 lines" in prompt

    # Empty-string fallback rule documented
    assert "empty string" in prompt.lower()

    # Few-shot examples cover the dogfood stack (Python + PHP)
    assert "vault_cli/auth.py" in prompt
    assert "app/Http/Controllers/UserController.php" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Parser: new fields present
# ─────────────────────────────────────────────────────────────────────────────

def test_parser_extracts_original_and_suggested_snippets():
    """When the LLM produces both new fields, the parser keeps them."""
    raw = _mock_llm_json(
        [
            {
                "file": "vault_cli/auth.py",
                "line": 12,
                "body": "Hardcoded password — use env var.",
                "original_snippet": 'ADMIN_PASSWORD = "admin123"',
                "suggested_snippet": 'ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")',
            }
        ]
    )
    parsed = _parse_grade_json(raw)
    c = parsed["comments"][0]
    assert c["original_snippet"] == 'ADMIN_PASSWORD = "admin123"'
    assert c["suggested_snippet"] == 'ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")'
    assert c["body"] == "Hardcoded password — use env var."


def test_parser_defaults_missing_snippets_to_empty_string():
    """Backward compat: old LLM responses without the new fields still parse."""
    raw = _mock_llm_json(
        [
            {
                "file": "app/db.py",
                "line": 42,
                "body": "SQL injection risk.",
            }
        ]
    )
    parsed = _parse_grade_json(raw)
    c = parsed["comments"][0]
    assert c["original_snippet"] == ""
    assert c["suggested_snippet"] == ""
    assert c["body"] == "SQL injection risk."


def test_parser_defaults_null_snippets_to_empty_string():
    """LLM sometimes emits JSON null instead of omitting the field."""
    raw = _mock_llm_json(
        [
            {
                "file": "app/db.py",
                "line": 42,
                "body": "General feedback.",
                "original_snippet": None,
                "suggested_snippet": None,
            }
        ]
    )
    parsed = _parse_grade_json(raw)
    c = parsed["comments"][0]
    assert c["original_snippet"] == ""
    assert c["suggested_snippet"] == ""


def test_parser_preserves_php_snippet_characters():
    """PHP snippets contain $ and escaped backslashes — round-trip cleanly."""
    php_original = (
        "public function store(Request $request) {\n"
        "    $user = User::create($request->all());\n"
        "    return redirect()->route('users.index');\n"
        "}"
    )
    php_suggested = (
        "public function store(StoreUserRequest $request) {\n"
        "    $user = User::create($request->validated());\n"
        "    return redirect()->route('users.index');\n"
        "}"
    )
    raw = _mock_llm_json(
        [
            {
                "file": "app/Http/Controllers/UserController.php",
                "line": 24,
                "body": "Use a FormRequest.",
                "original_snippet": php_original,
                "suggested_snippet": php_suggested,
            }
        ]
    )
    parsed = _parse_grade_json(raw)
    c = parsed["comments"][0]
    assert c["original_snippet"] == php_original
    assert c["suggested_snippet"] == php_suggested
    assert "$request->validated()" in c["suggested_snippet"]


def test_parser_rejects_malformed_json():
    """Existing error path: non-JSON from the LLM → 502."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _parse_grade_json("not valid json at all")
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error"] == "llm_upstream_failed"


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end /grade with mocked LLM — snippet fields flow through
# ─────────────────────────────────────────────────────────────────────────────

def test_grade_endpoint_returns_snippets_in_response():
    """Mocked LLM returns snippet pair → response body carries it through."""
    llm_json = _mock_llm_json(
        [
            {
                "file": "vault_cli/auth.py",
                "line": 12,
                "body": "Student-A, do not hardcode passwords.",
                "original_snippet": 'ADMIN_PASSWORD = "admin123"',
                "suggested_snippet": (
                    'ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")\n'
                    "if not ADMIN_PASSWORD:\n"
                    '    raise RuntimeError("Set ADMIN_PASSWORD env var")'
                ),
            }
        ]
    )

    mock_call = AsyncMock(return_value=(llm_json, 100, 50))
    with patch("app.api.grading.LLMAdapter") as adapter_cls:
        instance = adapter_cls.return_value
        instance.model_name = "claude-sonnet-4-5"
        instance.call_raw = mock_call

        resp = client.post("/api/v1/grade", json=_base_payload())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["comments"]) == 1
    c = body["comments"][0]
    assert c["original_snippet"] == 'ADMIN_PASSWORD = "admin123"'
    assert "os.environ.get" in c["suggested_snippet"]


def test_grade_endpoint_backward_compat_empty_snippets():
    """Mocked LLM omits new fields → response defaults them to "" (no crash)."""
    llm_json = _mock_llm_json(
        [
            {
                "file": "app/db.py",
                "line": 42,
                "body": "General design feedback.",
            }
        ]
    )

    mock_call = AsyncMock(return_value=(llm_json, 100, 50))
    with patch("app.api.grading.LLMAdapter") as adapter_cls:
        instance = adapter_cls.return_value
        instance.model_name = "claude-sonnet-4-5"
        instance.call_raw = mock_call

        resp = client.post("/api/v1/grade", json=_base_payload())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    c = body["comments"][0]
    assert c["original_snippet"] == ""
    assert c["suggested_snippet"] == ""


def test_grade_endpoint_malformed_json_returns_502():
    """Mocked LLM returns garbage → 502 llm_upstream_failed."""
    mock_call = AsyncMock(return_value=("this is not json", 10, 5))
    with patch("app.api.grading.LLMAdapter") as adapter_cls:
        instance = adapter_cls.return_value
        instance.model_name = "claude-sonnet-4-5"
        instance.call_raw = mock_call

        resp = client.post("/api/v1/grade", json=_base_payload())

    assert resp.status_code == 502
    assert resp.json()["detail"]["error"] == "llm_upstream_failed"
