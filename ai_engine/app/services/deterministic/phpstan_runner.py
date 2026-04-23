"""
phpstan runner — PHP Layer 1 static analyser (level 5).

Unlike phpcs which runs per-file on stdin, phpstan needs cross-file type
resolution and therefore runs once per PROJECT root. The caller supplies
the project root + the list of changed `.php` files; we filter the
report so only findings attached to changed files are returned.

Graceful-degradation envelope matches PhpcsRunner: any failure (binary
missing, timeout, invalid JSON, missing root) → [] and keep going.
Layer 1 is shadow-mode infra, never blocks the LLM pipeline.

PHP Day 3 of the Leera v0.9 PHP workstream.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Union

from .base import DeterministicFinding

logger = logging.getLogger(__name__)


# Phpstan doesn't expose stable rule IDs the way phpcs does — error
# messages are prose. We pattern-match on keywords in the message to
# bucket findings into the skill taxonomy. Ordering matters: earlier
# entries win, so put the specific patterns first.
_CATEGORY_PATTERNS: Sequence[tuple[Sequence[str], str]] = (
    # error_handling: null safety, undefined calls/props, empty catch
    (
        (
            r"null value",
            r"could be null",
            r"accessing property .* on null",
            r"on null",
            r"undefined method",
            r"does not exist",
            r"unknown method",
            r"unused catch",
            r"empty catch",
        ),
        "error_handling",
    ),
    # security: tainted data / injection signals from phpstan extensions
    (
        (r"tainted", r"sql injection", r"\bxss\b"),
        "security",
    ),
    # code_craft: types, signatures, inheritance, unused code
    (
        (
            r"invalid type",
            r"incompatible types?",
            r"wrong type",
            r"invoked with",
            r"method signature",
            r"incompatible return type",
            r"covariant",
            r"unused variable",
            r"unused parameter",
            r"unreachable",
        ),
        "code_craft",
    ),
)
_DEFAULT_CATEGORY = "code_craft"


def _category_for(message: str) -> str:
    """Pattern-match a phpstan message to our skill taxonomy."""
    lowered = (message or "").lower()
    for patterns, category in _CATEGORY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, lowered):
                return category
    return _DEFAULT_CATEGORY


def _severity_for(msg: dict) -> str:
    """Map a phpstan message dict to our severity enum.

    Phpstan doesn't emit per-message severities in its default JSON
    format. Level-5 findings are real type/null bugs but not critical
    security issues, so they map to "warning". Non-ignorable messages
    (phpstan flags them as structural) escalate to "error"-ish territory,
    which we express as "warning" as well — reserve "critical" for
    security extensions later.
    """
    if msg.get("ignorable") is False:
        return "warning"
    return "warning"


class PhpstanRunner:
    """Runs phpstan on a PHP project, returns findings for changed files."""

    name = "phpstan"

    # Phpstan needs more time than phpcs because it does cross-file
    # type resolution. 30s is ample for a typical student PR.
    DEFAULT_TIMEOUT_S = 30.0
    DEFAULT_LEVEL = "5"

    def __init__(
        self,
        *,
        binary: str = "phpstan",
        level: str = DEFAULT_LEVEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        extra_args: Optional[Sequence[str]] = None,
    ):
        self.binary = binary
        self.level = level
        self.timeout_s = timeout_s
        self.extra_args = list(extra_args or [])

    def run(
        self,
        project_root: Union[str, Path],
        changed_files: Optional[Sequence[str]] = None,
    ) -> List[DeterministicFinding]:
        """Run phpstan over `project_root`, filter to `changed_files`.

        If `changed_files` is provided, phpstan is told to analyse only
        those paths AND we also post-filter the JSON report, because
        phpstan may still surface cross-file findings attached to
        unchanged files when bootstrapping.
        """
        root = Path(project_root)
        if not root.is_dir():
            return []

        # Respect the teacher's phpstan.neon/neon.dist if present — they
        # set the level there. We only pass --level when no config exists.
        has_config = (root / "phpstan.neon").is_file() or (
            root / "phpstan.neon.dist"
        ).is_file()

        cmd: List[str] = [
            self.binary,
            "analyse",
            "--error-format=json",
            "--no-progress",
            "--no-interaction",
        ]
        if not has_config:
            cmd.append(f"--level={self.level}")

        if changed_files:
            cmd.extend(str(Path(f)) for f in changed_files)
        else:
            cmd.append(str(root))

        cmd.extend(self.extra_args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
                cwd=str(root),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("phpstan runner failed for %s: %s", project_root, exc)
            return []

        stdout = (result.stdout or b"").decode("utf-8", errors="replace").strip()
        if not stdout:
            return []

        return self._parse(stdout, root, changed_files)

    @staticmethod
    def _parse(
        stdout: str,
        project_root: Path,
        changed_files: Optional[Sequence[str]],
    ) -> List[DeterministicFinding]:
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("phpstan produced invalid JSON: %r", stdout[:200])
            return []

        files = (report or {}).get("files") or {}

        # Build a set of resolved changed-file paths for membership checks.
        changed_set: Optional[set[str]] = None
        if changed_files:
            resolved: set[str] = set()
            for f in changed_files:
                p = Path(f)
                try:
                    resolved.add(str(p.resolve() if p.is_absolute() else (project_root / p).resolve()))
                except OSError:
                    # resolve() can fail on non-existent paths on some platforms;
                    # fall back to the unresolved string.
                    resolved.add(str((project_root / p) if not p.is_absolute() else p))
            changed_set = resolved

        findings: List[DeterministicFinding] = []
        for fpath, file_data in files.items():
            if changed_set is not None:
                try:
                    abs_path = str(Path(fpath).resolve())
                except OSError:
                    abs_path = str(Path(fpath))
                if abs_path not in changed_set:
                    continue

            for msg in (file_data or {}).get("messages") or []:
                message_text = msg.get("message") or ""
                line = int(msg.get("line") or 0)
                # Newer phpstan (>=1.11) emits an `identifier` per message.
                # Older versions don't — fall back to a stable generic id.
                rule_id = msg.get("identifier") or "phpstan.generic"
                findings.append(
                    DeterministicFinding(
                        runner="phpstan",
                        rule_id=rule_id,
                        message=message_text,
                        severity=_severity_for(msg),
                        file_path=fpath,
                        line_start=line,
                        line_end=line,
                    )
                )
        return findings

    # Public alias so callers / tests can look up the taxonomy bucket
    # for a phpstan message without instantiating a runner.
    @staticmethod
    def category_for(message: str) -> str:
        return _category_for(message)
