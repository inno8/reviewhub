"""
Shared interface for Layer 1 deterministic runners.

A runner takes a file path + source text and returns a list of
DeterministicFinding dataclasses. The ai_engine pipeline later POSTs
these to Django as DeterministicFinding rows via the internal API.

Design note: runners MUST be side-effect free except for shelling out
to a linter. They run in parallel with the LLM call; if a runner crashes
or times out, the LLM path is unaffected (log-and-drop behaviour).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Protocol, List


@dataclass
class DeterministicFinding:
    """One Layer 1 finding produced by a runner."""

    runner: str              # "ruff" | "eslint"
    rule_id: str             # e.g. "E501", "no-unused-vars"
    message: str
    severity: str            # "critical" | "warning" | "info" | "suggestion"
    file_path: str
    line_start: int
    line_end: int

    def as_payload(self) -> dict:
        """Serialize for the internal Django API."""
        return asdict(self)


class DeterministicRunner(Protocol):
    """All Layer 1 runners share this tiny interface."""

    name: str

    def supports(self, file_path: str) -> bool: ...

    def run(self, file_path: str, source: str) -> List[DeterministicFinding]: ...


# ─── file → runner dispatch ──────────────────────────────────────────────

_PY_EXT = (".py",)
_JS_TS_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def runner_for_path(
    file_path: str,
    *,
    ruff: Optional[DeterministicRunner] = None,
    eslint: Optional[DeterministicRunner] = None,
) -> Optional[DeterministicRunner]:
    """
    Return the appropriate runner for this file, or None if no runner
    applies. Keeps dispatch tiny + testable.
    """
    lower = file_path.lower()
    if ruff is not None and lower.endswith(_PY_EXT):
        return ruff
    if eslint is not None and any(lower.endswith(ext) for ext in _JS_TS_EXT):
        return eslint
    return None
