"""
Tests for template-based comment generation.

Scope B2 of Nakijken Copilot v1 — template library replaces bulk LLM
calls for the 55-65% of comments that are stock phrases.
"""
from __future__ import annotations

import pytest

from app.services import template_comments as tc


def test_library_has_at_least_30_templates():
    """We promised 30-40 templates in the scope doc."""
    assert tc.template_count() >= 30


def test_match_template_by_category_severity_subtype():
    finding = {
        "category": "readability",
        "severity": "warning",
        "subtype": "naming",
    }
    t = tc.match_template(finding)
    assert t is not None
    assert t.category == "readability"
    assert t.subtype == "naming"


def test_match_template_falls_back_when_subtype_unknown():
    """Unknown subtype + known (category,severity) should NOT match a
    subtype-specific template; the index key won't exist and no
    subtype=None fallback is registered for this pair — expect None."""
    finding = {
        "category": "readability",
        "severity": "warning",
        "subtype": "totally-invented-subtype",
    }
    # No (readability, warning, None) in library, so no match:
    assert tc.match_template(finding) is None


def test_match_template_returns_none_for_unknown_category():
    assert tc.match_template({
        "category": "alien-stuff", "severity": "warning", "subtype": None,
    }) is None


def test_bare_except_template_requires_matching_code():
    """bare_except template has a code_pattern; non-matching code → no template."""
    base = {"category": "error_handling", "severity": "warning", "subtype": "bare_except"}

    with_bare = {**base, "original_code": "try:\n    foo()\nexcept:\n    pass"}
    assert tc.match_template(with_bare) is not None

    without = {**base, "original_code": "try:\n    foo()\nexcept ValueError:\n    pass"}
    assert tc.match_template(without) is None


def test_sql_injection_template_requires_matching_code():
    base = {"category": "security", "severity": "critical", "subtype": "sql_injection"}
    hit = {**base, "original_code": 'cursor.execute(f"SELECT * FROM x WHERE id = {uid}")'}
    miss = {**base, "original_code": 'cursor.execute("SELECT 1", (1,))'}
    assert tc.match_template(hit) is not None
    assert tc.match_template(miss) is None


def test_render_fills_placeholders():
    template = tc.CommentTemplate(
        category="readability", severity="warning", subtype="naming",
        body="Rename `{symbol}` please.",
    )
    assert tc.render(template, {"symbol": "x"}) == "Rename `x` please."


def test_render_safe_defaults_missing_placeholders():
    template = tc.CommentTemplate(
        category="x", severity="info", subtype=None,
        body="The `{symbol}` has value `{value}`.",
    )
    assert tc.render(template, {}) == "The `this` has value `this`."


def test_try_render_returns_ready_comment():
    finding = {
        "category": "readability", "severity": "warning", "subtype": "naming",
        "symbol": "q",
    }
    out = tc.try_render(finding)
    assert out is not None
    assert "`q`" in out


def test_try_render_returns_none_when_no_match():
    out = tc.try_render({
        "category": "nope", "severity": "warning", "subtype": None,
    })
    assert out is None


def test_compute_template_hit_rate():
    findings = [
        {"category": "readability", "severity": "warning", "subtype": "naming"},     # hit
        {"category": "readability", "severity": "suggestion", "subtype": "naming"},  # hit
        {"category": "mystery", "severity": "warning", "subtype": None},             # miss
    ]
    rate = tc.compute_template_hit_rate(findings)
    assert rate == pytest.approx(2 / 3)


def test_compute_template_hit_rate_empty():
    assert tc.compute_template_hit_rate([]) == 0.0


def test_all_templates_have_nonempty_body():
    """Every template must have a non-empty body — guards against
    accidental blank entries when the library grows."""
    for t in tc._TEMPLATES:  # noqa: SLF001
        assert t.body.strip(), f"Empty body for {t.category}/{t.severity}/{t.subtype}"
        assert t.severity in {"critical", "warning", "info", "suggestion"}
