"""
Template-based comment generation.

Teacher-review data shows 55-65% of comments are stock phrases. This
module provides a ~35-entry template library keyed by
`(finding_category, severity, optional_subtype)`. When a finding matches
a template, we fill the template with diff context and use it directly
instead of burning an LLM call.

Integration: the grading draft generator calls `match_template(finding)`
first. If it returns a ready string, skip the LLM round-trip. Otherwise
fall back to the existing LLM path.

Metrics: `compute_template_hit_rate` reports the share of findings that
were served by templates. Exposed as a property on GradingSession (no
migration needed) — see `session.template_hit_rate` in the grading app.

Scope B2 of Nakijken Copilot v1 (hybrid architecture).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


# ─── Template definitions ───────────────────────────────────────────────
#
# Key shape: (category, severity, subtype) — subtype may be None.
# Placeholders in the `body` string are resolved from the `context` dict
# passed to `render`. Missing placeholders fall back to a neutral string.

@dataclass(frozen=True)
class CommentTemplate:
    category: str
    severity: str          # "critical" | "warning" | "info" | "suggestion"
    subtype: Optional[str]
    body: str
    # Optional regex that must match the original_code for this template
    # to apply. Lets us target specific syntactic patterns (e.g. `except:`).
    code_pattern: Optional[str] = None


_TEMPLATES: List[CommentTemplate] = [
    # ── readability / naming ────────────────────────────────────────────
    CommentTemplate(
        "readability", "warning", "naming",
        "Consider a more descriptive name than `{symbol}` — reviewers need to "
        "infer meaning at a glance, and single-letter or generic names force "
        "them to re-read the surrounding code.",
    ),
    CommentTemplate(
        "readability", "suggestion", "naming",
        "Rename `{symbol}` to something that reads at the call site. A good "
        "name documents intent without needing a comment.",
    ),
    CommentTemplate(
        "readability", "info", "magic_number",
        "Extract `{value}` into a named constant — magic numbers hide intent "
        "and make changes error-prone.",
    ),
    CommentTemplate(
        "readability", "warning", "long_function",
        "This function is doing too much. Consider splitting it — each function "
        "should do one thing and read top-to-bottom like a paragraph.",
    ),
    CommentTemplate(
        "readability", "info", "comment_redundant",
        "This comment restates what the code already says. Prefer comments that "
        "explain *why*, not *what*.",
    ),
    CommentTemplate(
        "readability", "suggestion", "dead_code",
        "Remove the unused `{symbol}` — dead code is a maintenance trap.",
    ),

    # ── error_handling ──────────────────────────────────────────────────
    CommentTemplate(
        "error_handling", "warning", "bare_except",
        "Bare `except:` swallows everything including `KeyboardInterrupt` and "
        "`SystemExit`. Catch the specific exception you can recover from.",
        code_pattern=r"except\s*:",
    ),
    CommentTemplate(
        "error_handling", "warning", "broad_except",
        "Catching `Exception` is too broad — it hides bugs. Catch the specific "
        "exception you can handle; let the rest propagate.",
    ),
    CommentTemplate(
        "error_handling", "critical", "swallowed_exception",
        "This `except` block catches the exception but does nothing with it. "
        "Either log it, recover, or re-raise — silently swallowing errors is "
        "one of the hardest bugs to diagnose later.",
    ),
    CommentTemplate(
        "error_handling", "warning", "missing_try",
        "This call can raise — wrap it in a try/except or document the "
        "contract so callers know the failure modes.",
    ),
    CommentTemplate(
        "error_handling", "info", "generic_error_message",
        "The error message `{value}` doesn't help a future reader debug this. "
        "Include *what* failed and *why* it matters.",
    ),

    # ── testing ─────────────────────────────────────────────────────────
    CommentTemplate(
        "testing", "warning", "missing_assertion",
        "This test doesn't assert anything — it will pass even if the code is "
        "broken. Add an assertion that actually verifies the behaviour you "
        "want to lock in.",
    ),
    CommentTemplate(
        "testing", "info", "test_no_arrange",
        "This test is hard to follow. Structure it as Arrange-Act-Assert: set "
        "up the inputs, run the code under test, then assert.",
    ),
    CommentTemplate(
        "testing", "suggestion", "test_name",
        "Rename this test so the name describes the behaviour it verifies — "
        "something like `test_<subject>_<condition>_<expected>`.",
    ),
    CommentTemplate(
        "testing", "warning", "mocking_too_much",
        "This test mocks so much of the system that it's really only testing "
        "the mocks. Consider narrowing the mock scope or writing an "
        "integration-level test instead.",
    ),
    CommentTemplate(
        "testing", "info", "test_duplication",
        "This test is nearly identical to a sibling — parametrize over the "
        "inputs instead of copy-pasting.",
    ),

    # ── security ────────────────────────────────────────────────────────
    CommentTemplate(
        "security", "critical", "sql_injection",
        "Never build SQL with string concatenation or f-strings. Use "
        "parameterized queries (`?` placeholders) — this is one of the most "
        "exploited vulnerability classes in the world.",
        # Flag unsafe interpolation only: f-string, %, or + concat inside execute/query.
        code_pattern=r"(execute|query)\s*\(\s*([fF]['\"]|['\"][^'\"]*['\"]\s*[+%])",
    ),
    CommentTemplate(
        "security", "critical", "hardcoded_secret",
        "Hardcoded secrets in source get committed, leaked, and scraped. Move "
        "`{symbol}` to an environment variable or secret manager.",
    ),
    CommentTemplate(
        "security", "warning", "unvalidated_input",
        "Input from `{symbol}` is used directly without validation. Reject "
        "unexpected shapes at the boundary — validation is cheaper than "
        "debugging downstream crashes.",
    ),
    CommentTemplate(
        "security", "critical", "xss",
        "Rendering user-supplied HTML without escaping exposes XSS. Escape at "
        "render time or use a template engine that auto-escapes.",
    ),
    CommentTemplate(
        "security", "warning", "weak_crypto",
        "`{symbol}` is considered cryptographically weak. Use a modern "
        "primitive (e.g. SHA-256 / AES-GCM / Argon2 for passwords).",
    ),

    # ── performance ─────────────────────────────────────────────────────
    CommentTemplate(
        "performance", "warning", "n_plus_1",
        "This looks like an N+1 query — you're issuing one query per item in "
        "the loop. Batch with `select_related` / `prefetch_related` or a "
        "single query against the whole set.",
    ),
    CommentTemplate(
        "performance", "info", "repeated_computation",
        "`{symbol}` is recomputed every iteration. Hoist it out of the loop.",
    ),
    CommentTemplate(
        "performance", "suggestion", "premature_optimization",
        "This optimization adds complexity without clear evidence it's needed. "
        "Measure first, then optimize.",
    ),
    CommentTemplate(
        "performance", "warning", "blocking_io",
        "Blocking I/O inside an async handler stalls the event loop. Use an "
        "async client or `run_in_executor`.",
    ),

    # ── structure / architecture ────────────────────────────────────────
    CommentTemplate(
        "structure", "warning", "tight_coupling",
        "This module reaches directly into `{symbol}`. Depend on an interface "
        "instead — it makes the code testable and easier to change.",
    ),
    CommentTemplate(
        "structure", "info", "god_class",
        "This class has grown to handle many unrelated concerns. Split along "
        "the axis of change — one reason to edit per class.",
    ),
    CommentTemplate(
        "structure", "suggestion", "duplication",
        "This block is duplicated near `{location}`. Extract to a helper once "
        "you see it the third time.",
    ),
    CommentTemplate(
        "structure", "warning", "circular_import",
        "Circular import between `{symbol}` and the current module. Break the "
        "cycle by extracting the shared type into its own module.",
    ),

    # ── style / formatting ──────────────────────────────────────────────
    CommentTemplate(
        "style", "info", "line_too_long",
        "Line exceeds the project line limit. Wrap at argument boundaries for "
        "readability.",
    ),
    CommentTemplate(
        "style", "suggestion", "import_order",
        "Group imports: stdlib, third-party, local. Most linters auto-fix this.",
    ),
    CommentTemplate(
        "style", "info", "trailing_whitespace",
        "Trailing whitespace — most editors can strip this on save.",
    ),

    # ── documentation ───────────────────────────────────────────────────
    CommentTemplate(
        "documentation", "suggestion", "missing_docstring",
        "Public function `{symbol}` has no docstring. A one-line summary plus "
        "param/return types is enough for most cases.",
    ),
    CommentTemplate(
        "documentation", "info", "outdated_docstring",
        "The docstring on `{symbol}` no longer matches the signature — update "
        "or delete it.",
    ),

    # ── type safety ─────────────────────────────────────────────────────
    CommentTemplate(
        "types", "warning", "missing_type_hint",
        "Add type hints to `{symbol}` — they document the contract and let the "
        "type checker catch a whole class of bugs before runtime.",
    ),
    CommentTemplate(
        "types", "info", "any_type",
        "`{symbol}` is typed as `Any` / `unknown`, which defeats the type "
        "checker. Narrow it to the real type.",
    ),
]


# ─── Lookup index ───────────────────────────────────────────────────────

def _index(templates: Iterable[CommentTemplate]) -> Dict[Tuple[str, str, Optional[str]], CommentTemplate]:
    return {(t.category, t.severity, t.subtype): t for t in templates}


_INDEX = _index(_TEMPLATES)


# ─── Public API ─────────────────────────────────────────────────────────

def match_template(
    finding: dict,
) -> Optional[CommentTemplate]:
    """
    Find a matching template for this finding, or None.

    `finding` shape (matches the existing LLM Finding schema):
      {
        "category": "readability" | "error_handling" | ...,
        "severity": "critical" | "warning" | "info" | "suggestion",
        "subtype": Optional[str],
        "original_code": Optional[str],
        ...
      }
    """
    category = (finding.get("category") or "").strip().lower()
    severity = (finding.get("severity") or "").strip().lower()
    subtype = finding.get("subtype")
    if subtype is not None:
        subtype = str(subtype).strip().lower() or None

    # Exact match with subtype → fall back to category+severity only.
    t = _INDEX.get((category, severity, subtype))
    if t is None and subtype is not None:
        t = _INDEX.get((category, severity, None))
    if t is None:
        return None

    # If the template has a code pattern requirement, enforce it.
    if t.code_pattern:
        code = finding.get("original_code") or ""
        if not re.search(t.code_pattern, code):
            return None

    return t


def render(template: CommentTemplate, context: dict) -> str:
    """
    Fill template placeholders from the context dict. Missing keys fall
    back to a neutral 'this' so the comment stays readable.
    """
    class _SafeDict(dict):
        def __missing__(self, key):
            return "this"

    return template.body.format_map(_SafeDict(context or {}))


def try_render(finding: dict) -> Optional[str]:
    """
    One-shot helper: returns a ready-to-post comment, or None if no
    template matched. The grading draft generator calls this BEFORE
    burning an LLM call.
    """
    t = match_template(finding)
    if t is None:
        return None
    # Context comes from any fields the LLM extractor populated:
    ctx = {
        "symbol": finding.get("symbol") or finding.get("name") or "this",
        "value": finding.get("value") or "this",
        "location": finding.get("location") or "nearby",
    }
    return render(t, ctx)


def compute_template_hit_rate(findings: Iterable[dict]) -> float:
    """
    Returns the share of findings (0.0-1.0) that a template would serve.
    Used as a read-only metric on GradingSession (no DB field needed —
    compute from ai_draft_comments at read time).
    """
    total = 0
    hits = 0
    for f in findings:
        total += 1
        if match_template(f) is not None:
            hits += 1
    if total == 0:
        return 0.0
    return hits / total


def template_count() -> int:
    """Count of registered templates (for tests + observability)."""
    return len(_TEMPLATES)
