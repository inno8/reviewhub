"""
phpcs runner — PHP Layer 1 linter (PSR-12 ruleset).

Shells out to `phpcs --standard=PSR12 --report=json --no-colors -` with
the file source piped on stdin. Parses the `files` object in the JSON
report and emits one DeterministicFinding per message.

Same safety envelope as the ruff/eslint runners: any failure (binary
missing, timeout, invalid JSON, crash) is swallowed and logged — Layer 1
is shadow-mode infrastructure, never blocks the LLM pipeline.

PHP Day 2 of the Leera v0.9 PHP workstream.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import List, Optional, Sequence

from .base import DeterministicFinding

logger = logging.getLogger(__name__)


# phpcs "type" field → our severity enum.
# phpcs emits ERROR and WARNING; we fold anything unknown into "info".
def _severity_for(phpcs_type: str) -> str:
    t = (phpcs_type or "").upper()
    if t == "ERROR":
        return "warning"   # PSR-12 style errors are not critical bugs
    if t == "WARNING":
        return "info"
    return "suggestion"


# Map phpcs sniff prefixes → our skill taxonomy. PSR-12 is pure style, so
# everything defaults to "readability". Framework-specific sniffs may add
# other categories in Day 4 calibration; keeping the table explicit keeps
# the dispatch trivial to audit.
_CATEGORY_MAP = {
    "PSR12.Classes": "readability",
    "PSR12.ControlStructures": "readability",
    "PSR12.Files": "readability",
    "PSR12.Functions": "readability",
    "PSR12.Keywords": "readability",
    "PSR12.Namespaces": "readability",
    "PSR12.Operators": "readability",
    "PSR12.Properties": "readability",
    "PSR12.Traits": "readability",
    "PSR2": "readability",
    "PSR1": "readability",
    "Squiz": "readability",
    "Generic.Files.LineLength": "readability",
    "Generic.WhiteSpace": "readability",
    "Generic": "readability",
}
_DEFAULT_CATEGORY = "readability"


def _category_for(rule_id: str) -> str:
    # Longest-prefix match so "PSR12.Classes" wins over a hypothetical "PSR12".
    for prefix, category in sorted(_CATEGORY_MAP.items(), key=lambda kv: -len(kv[0])):
        if rule_id.startswith(prefix):
            return category
    return _DEFAULT_CATEGORY


class PhpcsRunner:
    """Runs `phpcs` against a single PHP file's source text."""

    name = "phpcs"

    def __init__(
        self,
        *,
        binary: str = "phpcs",
        standard: str = "PSR12",
        timeout_s: float = 5.0,
        extra_args: Optional[Sequence[str]] = None,
    ):
        self.binary = binary
        self.standard = standard
        self.timeout_s = timeout_s
        self.extra_args = list(extra_args or [])

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith(".php")

    def run(self, file_path: str, source: str) -> List[DeterministicFinding]:
        if not self.supports(file_path):
            return []

        cmd = [
            self.binary,
            f"--standard={self.standard}",
            "--report=json",
            "--no-colors",
            f"--stdin-path={file_path}",
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
            logger.warning("phpcs runner failed for %s: %s", file_path, exc)
            return []

        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        if not stdout:
            return []
        return self._parse(stdout, file_path)

    @staticmethod
    def _parse(stdout: str, file_path: str) -> List[DeterministicFinding]:
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("phpcs produced invalid JSON: %r", stdout[:200])
            return []

        findings: List[DeterministicFinding] = []
        files = (report or {}).get("files") or {}
        for fname, file_data in files.items():
            messages = (file_data or {}).get("messages") or []
            for msg in messages:
                rule_id = msg.get("source") or "unknown"
                line = int(msg.get("line") or 1)
                findings.append(
                    DeterministicFinding(
                        runner="phpcs",
                        rule_id=rule_id,
                        message=msg.get("message") or "",
                        severity=_severity_for(msg.get("type", "")),
                        file_path=fname or file_path,
                        line_start=line,
                        line_end=line,
                    )
                )
        # phpcs attaches a non-standard "category" concept; we store it
        # implicitly via rule_id + the mapping helper. Expose it for callers
        # that want it (e.g. skill-graph binding) without fattening the
        # DeterministicFinding dataclass.
        return findings

    # Exposed as a classmethod so tests (and the pipeline) can look up the
    # taxonomy bucket for a rule without instantiating a runner.
    @staticmethod
    def category_for(rule_id: str) -> str:
        return _category_for(rule_id)
