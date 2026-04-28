"""
Tests for Layer 1 deterministic runners (ruff, ESLint).

Scope B2 of Nakijken Copilot v1 — hybrid architecture. Runners are
shadow-mode; tests verify parsing, dispatch, and graceful failure when
the underlying binary is missing.
"""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.deterministic.base import (
    DeterministicFinding,
    runner_for_path,
)
from app.services.deterministic.ruff_runner import RuffRunner
from app.services.deterministic.eslint_runner import ESLintRunner


# ── dispatch ────────────────────────────────────────────────────────────

def test_runner_for_path_dispatches_python_to_ruff():
    ruff = RuffRunner()
    eslint = ESLintRunner()
    assert runner_for_path("app/db.py", ruff=ruff, eslint=eslint) is ruff
    assert runner_for_path("pkg/module/helper.py", ruff=ruff, eslint=eslint) is ruff


def test_runner_for_path_dispatches_js_ts_to_eslint():
    ruff = RuffRunner()
    eslint = ESLintRunner()
    for name in ("a.js", "b.jsx", "c.ts", "d.tsx", "e.mjs", "f.cjs"):
        assert runner_for_path(name, ruff=ruff, eslint=eslint) is eslint, name


def test_runner_for_path_returns_none_for_unsupported():
    ruff = RuffRunner()
    eslint = ESLintRunner()
    for name in ("README.md", "data.json", "a.go", "b.rs"):
        assert runner_for_path(name, ruff=ruff, eslint=eslint) is None, name


# ── ruff parsing ────────────────────────────────────────────────────────

RUFF_SAMPLE = json.dumps([
    {
        "code": "F401",
        "message": "`os` imported but unused",
        "filename": "app/x.py",
        "location": {"row": 1, "column": 1},
        "end_location": {"row": 1, "column": 10},
    },
    {
        "code": "S101",
        "message": "Use of assert detected",
        "filename": "app/x.py",
        "location": {"row": 5, "column": 1},
        "end_location": {"row": 5, "column": 20},
    },
])


def test_ruff_parses_valid_output():
    findings = RuffRunner._parse(RUFF_SAMPLE, "app/x.py")
    assert len(findings) == 2
    assert findings[0].runner == "ruff"
    assert findings[0].rule_id == "F401"
    assert findings[0].severity == "warning"      # F prefix
    assert findings[1].rule_id == "S101"
    assert findings[1].severity == "critical"     # S prefix → security


def test_ruff_parse_handles_invalid_json():
    findings = RuffRunner._parse("not-json-at-all", "app/x.py")
    assert findings == []


def test_ruff_run_swallows_missing_binary(tmp_path):
    runner = RuffRunner(binary="/definitely/not/a/real/ruff/binary/path/xyzzy")
    findings = runner.run("foo.py", "import os\n")
    assert findings == []


def test_ruff_supports_only_python():
    runner = RuffRunner()
    assert runner.supports("x.py") is True
    assert runner.supports("x.js") is False
    assert runner.supports("x.md") is False


def test_ruff_run_mocks_subprocess(monkeypatch):
    """Verify we call subprocess.run correctly and parse its stdout."""
    def fake_run(cmd, input, capture_output, timeout, check):
        assert "check" in cmd
        assert "--output-format=json" in cmd
        return SimpleNamespace(stdout=RUFF_SAMPLE.encode("utf-8"), stderr=b"", returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = RuffRunner()
    findings = runner.run("app/x.py", "import os\n")
    assert len(findings) == 2


# ── eslint parsing ──────────────────────────────────────────────────────

ESLINT_SAMPLE = json.dumps([
    {
        "filePath": "/tmp/a.js",
        "messages": [
            {"ruleId": "no-unused-vars", "severity": 2,
             "message": "'x' is defined but never used.",
             "line": 3, "endLine": 3},
            {"ruleId": "security/detect-eval-with-expression", "severity": 2,
             "message": "eval with expression", "line": 7, "endLine": 7},
            {"ruleId": None, "severity": 0,  # should be filtered
             "message": "off", "line": 1, "endLine": 1},
        ],
    }
])


def test_eslint_parses_valid_output():
    findings = ESLintRunner._parse(ESLINT_SAMPLE, "/tmp/a.js")
    assert len(findings) == 2
    assert findings[0].rule_id == "no-unused-vars"
    assert findings[0].severity == "warning"         # raw severity 2 → warning
    assert findings[1].rule_id == "security/detect-eval-with-expression"
    assert findings[1].severity == "critical"        # security/ prefix


def test_eslint_parse_handles_invalid_json():
    assert ESLintRunner._parse("oops", "/tmp/a.js") == []


def test_eslint_run_swallows_missing_binary():
    runner = ESLintRunner(binary="/definitely/not/a/real/eslint/xyzzy")
    assert runner.run("x.js", "var x = 1;") == []


def test_eslint_supports_js_ts_only():
    r = ESLintRunner()
    for good in ("a.js", "a.jsx", "a.ts", "a.tsx", "a.mjs", "a.cjs"):
        assert r.supports(good) is True
    for bad in ("a.py", "a.go", "README.md"):
        assert r.supports(bad) is False


# ── pipeline integration ────────────────────────────────────────────────

def test_run_layer1_runners_skips_unsupported_files(monkeypatch):
    """The pipeline must ignore files no runner handles."""
    from app.services import deterministic_pipeline as pipeline

    findings = pipeline.run_layer1_runners(
        [("README.md", "# hi\n"), ("notes.txt", "stuff")],
    )
    assert findings == []


def test_run_layer1_runners_calls_matching_runner():
    """Pipeline hands the .py file to ruff and aggregates results."""
    from app.services import deterministic_pipeline as pipeline

    class _FakeRuff:
        name = "ruff"
        def supports(self, p): return p.endswith(".py")
        def run(self, path, src):
            return [DeterministicFinding(
                runner="ruff", rule_id="X1", message="m",
                severity="warning", file_path=path, line_start=1, line_end=1,
            )]

    class _FakeESLint:
        name = "eslint"
        def supports(self, p): return p.endswith(".js")
        def run(self, path, src):
            return []

    out = pipeline.run_layer1_runners(
        [("a.py", "pass\n"), ("b.md", "nope")],
        ruff=_FakeRuff(), eslint=_FakeESLint(),
    )
    assert len(out) == 1
    assert out[0].runner == "ruff"
    assert out[0].file_path == "a.py"
