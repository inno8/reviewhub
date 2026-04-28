"""
Tests for the phpstan Layer 1 runner (PHP Workstream Day 3).

Covers:
- JSON report parsing + flattening
- changed-file filtering (phpstan may report findings in unchanged files
  because of cross-file type resolution)
- respects phpstan.neon / phpstan.neon.dist when present — no --level flag
- default level 5 when no config
- category mapping via message pattern-match (null / types / unused)
- graceful failure (missing binary, timeout, invalid JSON, empty stdout,
  missing project root)
- pipeline integration (PHP files → phpstan fires once per project)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.deterministic.base import DeterministicFinding
from app.services.deterministic.phpstan_runner import (
    PhpstanRunner,
    _category_for,
    _DEFAULT_CATEGORY,
)


# ── fixture data ────────────────────────────────────────────────────────

def _report_json(files: dict) -> str:
    return json.dumps({
        "totals": {"errors": sum(len(fd.get("messages", [])) for fd in files.values()),
                   "file_errors": len(files)},
        "files": files,
    })


def _fake_proc(stdout: str, returncode: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["phpstan"], returncode=returncode,
        stdout=stdout.encode("utf-8"), stderr=b"",
    )


# ── parsing ─────────────────────────────────────────────────────────────

def test_run_parses_phpstan_json_into_findings(tmp_path: Path):
    stdout = _report_json({
        str(tmp_path / "src" / "A.php"): {
            "errors": 1,
            "messages": [{
                "message": "Access to property $name on null value.",
                "line": 12,
                "identifier": "property.nonObject",
                "ignorable": True,
            }],
        },
    })
    runner = PhpstanRunner()
    with patch("subprocess.run", return_value=_fake_proc(stdout)):
        findings = runner.run(tmp_path)

    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, DeterministicFinding)
    assert f.runner == "phpstan"
    assert f.rule_id == "property.nonObject"
    assert f.line_start == 12 and f.line_end == 12
    assert "null" in f.message.lower()


# ── graceful failure ────────────────────────────────────────────────────

def test_run_returns_empty_when_binary_missing(tmp_path: Path):
    runner = PhpstanRunner(binary="phpstan-does-not-exist")
    with patch("subprocess.run", side_effect=FileNotFoundError("no phpstan")):
        assert runner.run(tmp_path) == []


def test_run_returns_empty_on_timeout(tmp_path: Path):
    runner = PhpstanRunner()
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="phpstan", timeout=30),
    ):
        assert runner.run(tmp_path) == []


def test_run_returns_empty_on_invalid_json(tmp_path: Path):
    runner = PhpstanRunner()
    with patch("subprocess.run", return_value=_fake_proc("<<<not json>>>")):
        assert runner.run(tmp_path) == []


def test_run_returns_empty_on_empty_stdout(tmp_path: Path):
    runner = PhpstanRunner()
    with patch("subprocess.run", return_value=_fake_proc("")):
        assert runner.run(tmp_path) == []


def test_run_returns_empty_when_project_root_missing(tmp_path: Path):
    runner = PhpstanRunner()
    ghost = tmp_path / "nope"
    # Must short-circuit before calling subprocess at all.
    with patch("subprocess.run") as mock_run:
        assert runner.run(ghost) == []
        mock_run.assert_not_called()


# ── changed-file filtering ──────────────────────────────────────────────

def test_run_filters_to_changed_files_only(tmp_path: Path):
    a = tmp_path / "A.php"
    b = tmp_path / "B.php"
    a.write_text("<?php\n")
    b.write_text("<?php\n")

    stdout = _report_json({
        str(a.resolve()): {
            "errors": 1,
            "messages": [{
                "message": "Method X::y() invoked with wrong types.",
                "line": 3, "identifier": "arguments.count", "ignorable": True,
            }],
        },
        str(b.resolve()): {
            "errors": 1,
            "messages": [{
                "message": "Unused variable $foo.",
                "line": 7, "identifier": "variable.unused", "ignorable": True,
            }],
        },
    })
    runner = PhpstanRunner()
    with patch("subprocess.run", return_value=_fake_proc(stdout)):
        # Only A.php was changed — B.php findings should be filtered out.
        findings = runner.run(tmp_path, changed_files=[str(a)])

    assert len(findings) == 1
    assert findings[0].file_path.endswith("A.php")


def test_run_reports_all_files_when_no_filter(tmp_path: Path):
    a = tmp_path / "A.php"
    b = tmp_path / "B.php"
    a.write_text("<?php\n")
    b.write_text("<?php\n")

    stdout = _report_json({
        str(a.resolve()): {"errors": 1, "messages": [{"message": "m1", "line": 1}]},
        str(b.resolve()): {"errors": 1, "messages": [{"message": "m2", "line": 1}]},
    })
    runner = PhpstanRunner()
    with patch("subprocess.run", return_value=_fake_proc(stdout)):
        findings = runner.run(tmp_path)
    assert len(findings) == 2


# ── config handling ─────────────────────────────────────────────────────

def test_run_respects_phpstan_neon_no_level_flag(tmp_path: Path):
    (tmp_path / "phpstan.neon").write_text("parameters:\n  level: 8\n")
    runner = PhpstanRunner()

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _fake_proc(_report_json({}))

    with patch("subprocess.run", side_effect=fake_run):
        runner.run(tmp_path)

    assert "--level=5" not in captured["cmd"]
    assert not any(str(c).startswith("--level") for c in captured["cmd"])


def test_run_respects_phpstan_neon_dist(tmp_path: Path):
    (tmp_path / "phpstan.neon.dist").write_text("parameters:\n  level: 6\n")
    runner = PhpstanRunner()
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _fake_proc(_report_json({}))

    with patch("subprocess.run", side_effect=fake_run):
        runner.run(tmp_path)

    assert not any(str(c).startswith("--level") for c in captured["cmd"])


def test_run_uses_default_level_5_when_no_config(tmp_path: Path):
    runner = PhpstanRunner()
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _fake_proc(_report_json({}))

    with patch("subprocess.run", side_effect=fake_run):
        runner.run(tmp_path)

    assert "--level=5" in captured["cmd"]


# ── category mapping ────────────────────────────────────────────────────

def test_category_null_access_maps_to_error_handling():
    assert _category_for("Access to property $x on null value.") == "error_handling"
    assert _category_for("Call to an undefined method Foo::bar().") == "error_handling"
    assert PhpstanRunner.category_for("Result could be null here") == "error_handling"


def test_category_type_mismatch_maps_to_code_craft():
    assert _category_for("Method Foo::bar() invoked with wrong types.") == "code_craft"
    assert _category_for("Incompatible return type string, int given.") == "code_craft"
    assert _category_for("Unused variable $x.") == "code_craft"


def test_category_tainted_maps_to_security():
    assert _category_for("Tainted data passed to database query.") == "security"


def test_category_unknown_falls_back_to_default():
    assert _category_for("A message we have never seen before.") == _DEFAULT_CATEGORY
    assert _DEFAULT_CATEGORY == "code_craft"


# ── pipeline integration ────────────────────────────────────────────────

def test_pipeline_fires_phpstan_once_for_php_diff(tmp_path: Path):
    from app.services.deterministic_pipeline import run_layer1_runners

    a = tmp_path / "Controller.php"
    a.write_text("<?php\nclass C {}\n")

    phpstan_stdout = _report_json({
        str(a.resolve()): {
            "errors": 1,
            "messages": [{
                "message": "Access to property on null.",
                "line": 2, "identifier": "property.nonObject", "ignorable": True,
            }],
        },
    })

    # phpcs returns nothing (we're isolating phpstan integration here)
    # but it WILL still be called per PHP file — we stub subprocess.run
    # to dispatch by binary name.
    def fake_run(cmd, **kwargs):
        if not cmd:
            return _fake_proc("")
        binary = str(cmd[0]).lower()
        if "phpstan" in binary:
            return _fake_proc(phpstan_stdout)
        # phpcs: return empty report
        return _fake_proc(json.dumps({"totals": {}, "files": {}}))

    with patch("subprocess.run", side_effect=fake_run):
        findings = run_layer1_runners(
            [(str(a), "<?php\nclass C {}\n")],
            project_root=str(tmp_path),
        )

    phpstan_findings = [f for f in findings if f.runner == "phpstan"]
    assert len(phpstan_findings) == 1
    assert phpstan_findings[0].rule_id == "property.nonObject"


def test_pipeline_skips_phpstan_when_no_project_root(tmp_path: Path):
    from app.services.deterministic_pipeline import run_layer1_runners

    a = tmp_path / "X.php"
    a.write_text("<?php\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(str(cmd[0]).lower() if cmd else "")
        return _fake_proc(json.dumps({"totals": {}, "files": {}}))

    with patch("subprocess.run", side_effect=fake_run):
        # No project_root supplied → phpstan must not fire.
        run_layer1_runners([(str(a), "<?php\n")])

    assert not any("phpstan" in c for c in calls)


def test_pipeline_skips_phpstan_when_no_php_in_diff(tmp_path: Path):
    from app.services.deterministic_pipeline import run_layer1_runners

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(str(cmd[0]).lower() if cmd else "")
        # Ruff/eslint return empty — we don't care about their shape here.
        return _fake_proc("")

    with patch("subprocess.run", side_effect=fake_run):
        run_layer1_runners(
            [("src/x.py", "print('x')\n")],
            project_root=str(tmp_path),
        )

    assert not any("phpstan" in c for c in calls)
