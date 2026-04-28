"""
ESLint runner — JS/TS Layer 1 linter.

Shells out to `eslint --stdin --stdin-filename <file> --format json`
and parses the result array. Same safety envelope as the ruff runner:
any failure is swallowed and logged, LLM pipeline is never blocked.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import List, Optional, Sequence

from .base import DeterministicFinding

logger = logging.getLogger(__name__)

# ESLint severity: 0 = off (filtered out), 1 = warning, 2 = error.
# Plus we escalate by rule name for well-known security rules.
_SECURITY_RULE_SUBSTRINGS = (
    "security/",
    "no-eval",
    "no-implied-eval",
    "no-new-func",
)


def _severity_for(rule_id: str, raw_severity: int) -> str:
    rid = rule_id or ""
    if any(s in rid for s in _SECURITY_RULE_SUBSTRINGS):
        return "critical"
    if raw_severity >= 2:
        return "warning"
    if raw_severity == 1:
        return "info"
    return "suggestion"


class ESLintRunner:
    """Runs `eslint` against a single file's source text via stdin."""

    name = "eslint"

    def __init__(
        self,
        *,
        binary: str = "eslint",
        timeout_s: float = 20.0,
        extra_args: Optional[Sequence[str]] = None,
    ):
        self.binary = binary
        self.timeout_s = timeout_s
        self.extra_args = list(extra_args or [])

    def supports(self, file_path: str) -> bool:
        lower = file_path.lower()
        return lower.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"))

    def run(self, file_path: str, source: str) -> List[DeterministicFinding]:
        if not self.supports(file_path):
            return []

        cmd = [
            self.binary,
            "--stdin",
            "--stdin-filename", file_path,
            "--format", "json",
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
            logger.warning("eslint runner failed for %s: %s", file_path, exc)
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
            logger.warning("eslint produced invalid JSON: %r", stdout[:200])
            return []

        findings: List[DeterministicFinding] = []
        # ESLint --format=json returns a list of per-file result objects.
        for file_result in raw:
            path = file_result.get("filePath") or file_path
            for msg in file_result.get("messages") or []:
                rule_id = msg.get("ruleId") or ""
                raw_sev = int(msg.get("severity") or 0)
                if raw_sev == 0:
                    continue
                line_start = int(msg.get("line") or 1)
                line_end = int(msg.get("endLine") or line_start)
                findings.append(
                    DeterministicFinding(
                        runner="eslint",
                        rule_id=rule_id or "unknown",
                        message=msg.get("message") or "",
                        severity=_severity_for(rule_id, raw_sev),
                        file_path=path,
                        line_start=line_start,
                        line_end=max(line_end, line_start),
                    )
                )
        return findings
