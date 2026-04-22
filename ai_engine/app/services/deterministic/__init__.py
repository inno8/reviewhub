"""
Layer 1 deterministic runners — ruff (Python), ESLint (JS/TS).

Scope B2 of Nakijken Copilot v1 hybrid architecture. Runners operate in
SHADOW MODE: findings are collected alongside the LLM pipeline and stored
as DeterministicFinding rows on the Django side, but NEVER surfaced to
teachers in v1. We use them to measure Layer 1 overlap with LLM findings
and decide when to swap the execution order.
"""
from .base import DeterministicFinding, DeterministicRunner, runner_for_path
from .ruff_runner import RuffRunner
from .eslint_runner import ESLintRunner
from .phpcs_runner import PhpcsRunner

__all__ = [
    "DeterministicFinding",
    "DeterministicRunner",
    "RuffRunner",
    "ESLintRunner",
    "PhpcsRunner",
    "runner_for_path",
]
