"""
Tests for the phpcs Layer 1 runner (PHP Workstream Day 2).

Covers:
- file-type dispatch via runner_for_path
- JSON report parsing + flattening across multiple files
- severity + category mapping
- graceful failure (binary missing, timeout, invalid JSON, empty stdout)
- pipeline integration (PHP file → phpcs, mixed with py/js)
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from app.services.deterministic.base import (
    DeterministicFinding,
    runner_for_path,
)
from app.services.deterministic.eslint_runner import ESLintRunner
from app.services.deterministic.phpcs_runner import PhpcsRunner, _category_for, _severity_for
from app.services.deterministic.ruff_runner import RuffRunner


# ── fixture data ────────────────────────────────────────────────────────

PHPCS_SAMPLE = json.dumps({
    "totals": {"errors": 2, "warnings": 1, "fixable": 1},
    "files": {
        "/src/Example.php": {
            "errors": 2,
            "warnings": 1,
            "messages": [
                {
                    "message": "Opening brace of a class must be on the line after the definition",
                    "source": "PSR12.Classes.ClassDeclaration.OpenBraceNewLine",
                    "severity": 5,
                    "fixable": True,
                    "type": "ERROR",
                    "line": 3,
                    "column": 32,
                },
                {
                    "message": "Line exceeds 120 characters; contains 142 characters",
                    "source": "Generic.Files.LineLength.TooLong",
                    "severity": 5,
                    "fixable": False,
                    "type": "ERROR",
                    "line": 15,
                    "column": 121,
                },
                {
                    "message": "Variable \"my_var\" is not in valid camel caps format",
                    "source": "Squiz.NamingConventions.ValidVariableName.NotCamelCaps",
                    "severity": 5,
                    "fixable": False,
                    "type": "WARNING",
                    "line": 22,
                    "column": 9,
                },
            ],
        },
    },
})


MULTIFILE_SAMPLE = json.dumps({
    "totals": {"errors": 2, "warnings": 0, "fixable": 0},
    "files": {
        "/src/A.php": {
            "errors": 1, "warnings": 0,
            "messages": [{
                "message": "A", "source": "PSR12.Files.OpenTag.NotAlone",
                "type": "ERROR", "line": 1, "column": 1,
            }],
        },
        "/src/B.php": {
            "errors": 1, "warnings": 0,
            "messages": [{
                "message": "B", "source": "PSR12.Namespaces.NamespaceDeclaration.BlankLineAfter",
                "type": "ERROR", "line": 4, "column": 1,
            }],
        },
    },
})


# ── dispatch ────────────────────────────────────────────────────────────

def test_runner_for_path_dispatches_php_to_phpcs():
    ruff = RuffRunner()
    eslint = ESLintRunner()
    phpcs = PhpcsRunner()
    assert runner_for_path("src/Controller.php", ruff=ruff, eslint=eslint, phpcs=phpcs) is phpcs
    assert runner_for_path("pkg/Service.PHP", ruff=ruff, eslint=eslint, phpcs=phpcs) is phpcs


def test_runner_for_path_php_none_when_phpcs_absent():
    ruff = RuffRunner()
    eslint = ESLintRunner()
    # No phpcs kwarg → dispatch must return None for .php files, not crash.
    assert runner_for_path("src/Controller.php", ruff=ruff, eslint=eslint) is None


def test_phpcs_runner_supports_only_php():
    p = PhpcsRunner()
    assert p.supports("a.php") is True
    assert p.supports("a.PHP") is True
    assert p.supports("a.py") is False
    assert p.supports("a.js") is False
    assert p.supports("README.md") is False


# ── severity + category mapping ─────────────────────────────────────────

def test_severity_maps_error_and_warning():
    # PSR-12 ERRORs are style — map to "warning" not "critical".
    assert _severity_for("ERROR") == "warning"
    assert _severity_for("WARNING") == "info"
    assert _severity_for("") == "suggestion"
    assert _severity_for("???") == "suggestion"


def test_category_psr12_classes_maps_to_readability():
    assert _category_for("PSR12.Classes.ClassDeclaration.OpenBraceNewLine") == "readability"


def test_category_generic_line_length_maps_to_readability():
    assert _category_for("Generic.Files.LineLength.TooLong") == "readability"


def test_category_unknown_rule_falls_back_to_default():
    assert _category_for("SomeVendor.Made.Up.Rule") == "readability"
    # PhpcsRunner.category_for is the public alias for the same helper.
    assert PhpcsRunner.category_for("Totally.Unknown") == "readability"


# ── parsing ─────────────────────────────────────────────────────────────

def _fake_proc(stdout: str, returncode: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["phpcs"], returncode=returncode,
        stdout=stdout.encode("utf-8"), stderr=b"",
    )


def test_run_parses_phpcs_json_into_findings():
    runner = PhpcsRunner()
    with patch("subprocess.run", return_value=_fake_proc(PHPCS_SAMPLE)):
        findings = runner.run("/src/Example.php", "<?php\n")

    assert len(findings) == 3
    assert all(isinstance(f, DeterministicFinding) for f in findings)
    assert all(f.runner == "phpcs" for f in findings)

    by_rule = {f.rule_id: f for f in findings}
    open_brace = by_rule["PSR12.Classes.ClassDeclaration.OpenBraceNewLine"]
    assert open_brace.severity == "warning"  # phpcs "ERROR" → our "warning"
    assert open_brace.line_start == 3
    assert open_brace.line_end == 3
    assert open_brace.file_path == "/src/Example.php"

    name_warn = by_rule["Squiz.NamingConventions.ValidVariableName.NotCamelCaps"]
    assert name_warn.severity == "info"  # phpcs "WARNING" → "info"


def test_run_flattens_multiple_files_in_report():
    runner = PhpcsRunner()
    with patch("subprocess.run", return_value=_fake_proc(MULTIFILE_SAMPLE)):
        findings = runner.run("/src/A.php", "<?php\n")
    assert {f.file_path for f in findings} == {"/src/A.php", "/src/B.php"}
    assert {f.rule_id for f in findings} == {
        "PSR12.Files.OpenTag.NotAlone",
        "PSR12.Namespaces.NamespaceDeclaration.BlankLineAfter",
    }


# ── graceful failure ────────────────────────────────────────────────────

def test_run_returns_empty_when_binary_missing():
    runner = PhpcsRunner(binary="phpcs-does-not-exist")
    with patch("subprocess.run", side_effect=FileNotFoundError("no phpcs")):
        assert runner.run("/src/x.php", "<?php\n") == []


def test_run_returns_empty_on_timeout():
    runner = PhpcsRunner()
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="phpcs", timeout=5),
    ):
        assert runner.run("/src/x.php", "<?php\n") == []


def test_run_returns_empty_on_invalid_json():
    runner = PhpcsRunner()
    with patch("subprocess.run", return_value=_fake_proc("not json {")):
        assert runner.run("/src/x.php", "<?php\n") == []


def test_run_returns_empty_on_empty_stdout():
    runner = PhpcsRunner()
    with patch("subprocess.run", return_value=_fake_proc("")):
        assert runner.run("/src/x.php", "<?php\n") == []


def test_run_returns_empty_for_non_php_file():
    runner = PhpcsRunner()
    # Must short-circuit before calling subprocess at all.
    with patch("subprocess.run") as mock_run:
        assert runner.run("/src/x.py", "print('x')") == []
        mock_run.assert_not_called()


def test_run_handles_report_with_no_messages():
    runner = PhpcsRunner()
    clean = json.dumps({"totals": {"errors": 0, "warnings": 0}, "files": {}})
    with patch("subprocess.run", return_value=_fake_proc(clean, returncode=0)):
        assert runner.run("/src/clean.php", "<?php\n") == []


# ── pipeline integration ────────────────────────────────────────────────

def test_run_layer1_runners_dispatches_php_to_phpcs():
    from app.services.deterministic_pipeline import run_layer1_runners

    # Stub phpcs so the pipeline doesn't shell out.
    runner = PhpcsRunner()
    with patch("subprocess.run", return_value=_fake_proc(PHPCS_SAMPLE)):
        findings = run_layer1_runners(
            [("/src/Example.php", "<?php\nclass X {}\n")],
            # ruff/eslint will default-construct and short-circuit on .php
            phpcs=runner,
        )
    assert len(findings) == 3
    assert {f.runner for f in findings} == {"phpcs"}
