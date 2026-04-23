"""
Tests for Scope B2 DeterministicFinding model + internal endpoint.

The model is additive and shadow-mode — no teacher-facing surface.
These tests lock in:
  - model persists + indexes correctly
  - internal endpoint accepts bulk findings
  - internal endpoint is gated by INTERNAL_API_KEY
  - validation rejects malformed payloads
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from evaluations.models import DeterministicFinding, Evaluation


@pytest.fixture
def deterministic_eval(db, test_user, test_project):
    return Evaluation.objects.create(
        project=test_project,
        author=test_user,
        commit_sha="deadbeef1234",
        commit_message="feat: test",
        branch="main",
        author_name="testdev",
        author_email="dev@test.com",
        overall_score=90.0,
        status="completed",
    )


def test_deterministic_finding_model_create(deterministic_eval):
    df = DeterministicFinding.objects.create(
        evaluation=deterministic_eval,
        runner=DeterministicFinding.Runner.RUFF,
        rule_id="E501",
        message="line too long",
        severity=DeterministicFinding.Severity.INFO,
        file_path="app/x.py",
        line_start=42,
        line_end=42,
    )
    assert df.pk is not None
    assert df.evaluation_id == deterministic_eval.id
    # Reverse relation works
    assert deterministic_eval.deterministic_findings.count() == 1


def test_internal_endpoint_rejects_without_api_key(deterministic_eval, settings):
    settings.DEBUG = False
    with patch.dict(os.environ, {"INTERNAL_API_KEY": "secret-key-123"}, clear=False):
        client = APIClient()
        resp = client.post(
            "/api/evaluations/internal/deterministic-findings/",
            {"evaluation_id": deterministic_eval.id, "findings": []},
            format="json",
        )
    assert resp.status_code in (401, 403)


def test_internal_endpoint_accepts_with_api_key(deterministic_eval):
    with patch.dict(os.environ, {"INTERNAL_API_KEY": "secret-key-123"}, clear=False):
        client = APIClient()
        payload = {
            "evaluation_id": deterministic_eval.id,
            "findings": [
                {
                    "runner": "ruff", "rule_id": "F401", "message": "unused import",
                    "severity": "warning", "file_path": "app/x.py",
                    "line_start": 1, "line_end": 1,
                },
                {
                    "runner": "eslint", "rule_id": "no-unused-vars",
                    "message": "x is defined but never used",
                    "severity": "warning", "file_path": "src/y.js",
                    "line_start": 3, "line_end": 3,
                },
            ],
        }
        resp = client.post(
            "/api/evaluations/internal/deterministic-findings/",
            payload, format="json",
            HTTP_X_API_KEY="secret-key-123",
        )

    assert resp.status_code == 201, resp.content
    assert resp.json()["created"] == 2
    assert DeterministicFinding.objects.filter(evaluation=deterministic_eval).count() == 2


def test_internal_endpoint_no_api_key_configured_is_open(deterministic_eval):
    """When INTERNAL_API_KEY is unset (dev mode) the endpoint falls back to AllowAny."""
    with patch.dict(os.environ, {"INTERNAL_API_KEY": ""}, clear=False):
        client = APIClient()
        resp = client.post(
            "/api/evaluations/internal/deterministic-findings/",
            {"evaluation_id": deterministic_eval.id, "findings": []},
            format="json",
        )
    assert resp.status_code == 201


def test_internal_endpoint_rejects_missing_evaluation_id():
    with patch.dict(os.environ, {"INTERNAL_API_KEY": ""}, clear=False):
        client = APIClient()
        resp = client.post(
            "/api/evaluations/internal/deterministic-findings/",
            {"findings": []}, format="json",
        )
    assert resp.status_code == 400


def test_internal_endpoint_rejects_invalid_finding_shape(deterministic_eval):
    with patch.dict(os.environ, {"INTERNAL_API_KEY": ""}, clear=False):
        client = APIClient()
        resp = client.post(
            "/api/evaluations/internal/deterministic-findings/",
            {
                "evaluation_id": deterministic_eval.id,
                "findings": [{"runner": "not-a-valid-runner"}],  # missing required fields
            },
            format="json",
        )
    assert resp.status_code == 400


def test_internal_endpoint_404_on_unknown_evaluation(db):
    with patch.dict(os.environ, {"INTERNAL_API_KEY": ""}, clear=False):
        client = APIClient()
        resp = client.post(
            "/api/evaluations/internal/deterministic-findings/",
            {"evaluation_id": 999999, "findings": []},
            format="json",
        )
    assert resp.status_code == 404
