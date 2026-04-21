"""
ruff runner — Python Layer 1 linter.

Shells out to `ruff check --output-format=json -` and parses the JSON
array. Any failure (binary missing, non-zero exit with invalid JSON,
timeout) is swallowed and logged: Layer 1 is shadow-mode infrastructure,
it must never break the LLM pipeline.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import List, Optional, Sequence

from .base import DeterministicFinding

logger = logging.getLogger(__name__)

# Map ruff severity-ish heuristics to our Finding severity enum.
# ruff reports a single "code" (e.g. E501) with no severity field in the
# default JSON output — categorize by rule prefix instead.
_CRITICAL_PREFIXES = ("S",)           # bandit-style security rules
_WARNING_PREFIXES = ("F", "E", "B", "PL")  # pyflakes, pycodestyle errors, bugbear, pylint
_INFO_PREFIXES = ("W", "I")                # warnings, isort
# everything else → suggestion


def _severity_for(rule_code: str) -> str:
    for prefix in _CRITICAL_PREFIXES:
        if rule_code.startswith(prefix):
            return "critical"
    for prefix in _WARNING_PREFIXES:
        if rule_code.startswith(prefix):
            return "warning"
    for prefix in _INFO_PREFIXES:
        if rule_code.startswith(prefix):
            return "info"
    return "suggestion"


class RuffRunner:
    """Runs `ruff` against a single file's source text."""

    name = "ruff"

    def __init__(
        self,
        *,
        binary: str = "ruff",
        timeout_s: float = 15.0,
        extra_args: Optional[Sequence[str]] = None,
    ):
        self.binary = binary
        self.timeout_s = timeout_s
        self.extra_args = list(extra_args or [])

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith(".py")

    def run(self, file_path: str, source: str) -> List[DeterministicFinding]:
        if not self.supports(file_path):
            return []

        cmd = [
            self.binary,
            "check",
            "--output-format=json",
            "--stdin-filename",
            file_path,
            "-",
            *self.extra_args,
        ]
        try:
            result = subprocess.run(
                cmd,
                input=source.encode("utf-8"),
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("ruff runner failed for %s: %s", file_path, exc)
            return []

        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        if not stdout:
            return []
        return self._parse(stdout, file_path)

    @staticmethod
    def _parse(stdout: str, file_path: str) -> List[DeterministicFinding]:
        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("ruff produced invalid JSON: %r", stdout[:200])
            return []

        findings: List[DeterministicFinding] = []
        for item in raw:
            code = item.get("code") or ""
            msg = item.get("message") or ""
            loc = item.get("location") or {}
            end_loc = item.get("end_location") or loc
            line_start = int(loc.get("row") or 1)
            line_end = int(end_loc.get("row") or line_start)
            findings.append(
                DeterministicFinding(
                    runner="ruff",
                    rule_id=code,
                    message=msg,
                    severity=_severity_for(code),
                    file_path=item.get("filename") or file_path,
                    line_start=line_start,
                    line_end=max(line_end, line_start),
                )
            )
        return findings
