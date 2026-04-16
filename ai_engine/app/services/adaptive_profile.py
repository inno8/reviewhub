"""
Phase 5 – Full Mentor / Adaptive Profile
Fetches the developer's skill profile + patterns from Django and builds an
enriched developer_history section to inject into LLM prompts.

This gives the LLM:
  - Developer level (beginner / intermediate / advanced)
  - Weak skill areas (focus attention here)
  - Strengths (acknowledge + reinforce)
  - Recurring patterns (recurring issues, with counts)
  - Personalized tone instructions per level
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

STRENGTH_THRESHOLD = 70   # skill score ≥ this → strength (0-100 scale)
WEAKNESS_THRESHOLD = 45   # skill score ≤ this → weakness
PATTERN_THRESHOLD = 3     # count ≥ this → "frequent"

LEVEL_INSTRUCTIONS = {
    "beginner": (
        "This is a beginner developer. Use simple language. "
        "Explain *why* each issue matters, not just what to fix. "
        "Prioritise at most 3 actionable findings."
    ),
    "intermediate": (
        "This is an intermediate developer. Be concise. "
        "Highlight best-practice gaps and architectural concerns. "
        "Suggest improvements and link to underlying principles."
    ),
    "advanced": (
        "This is an advanced developer. Be direct and succinct. "
        "Focus on subtle correctness issues, performance, security edge cases, "
        "and maintainability at scale."
    ),
}

LEARNING_STYLE_INSTRUCTIONS = {
    "short_tips": "Keep each finding explanation to 1-2 sentences. Use bullet points.",
    "detailed": "Provide thorough explanations with context and reasoning for each finding.",
    "examples": "Always include a code example in the suggested_code field. Explain with concrete before/after.",
    "challenges": "Frame findings as learning challenges. Ask 'can you spot why this is a problem?'",
}

GOAL_CONTEXT = {
    "get_job": "The developer is preparing for job interviews — highlight industry-standard practices.",
    "improve_job": "The developer wants to improve at their current role — focus on practical, immediate wins.",
    "become_senior": "The developer aims to become senior — emphasise architecture, patterns and code ownership.",
    "learn_new_tech": "The developer is learning new technology — be encouraging and explanatory.",
    "build_startup": "The developer is building a startup — balance speed with code quality pragmatically.",
}

PATTERN_RECOMMENDATIONS = {
    "missing_edge_cases": "Study defensive programming and boundary testing",
    "poor_error_handling": "Read error-handling best practices for your language",
    "no_input_validation": "Review OWASP input validation guidelines",
    "hardcoded_values": "Learn about configuration management and constants",
    "missing_tests": "Practice TDD by writing tests before code",
    "code_duplication": "Study the DRY principle and refactoring patterns",
    "security_exposure": "Take a secure-coding course for your stack",
    "performance_issues": "Learn profiling tools for your language",
}


def compute_level(avg_score: float, evaluation_count: int, experience_years: float = 0.0) -> str:
    """
    Derive developer level from aggregate skill score and experience.
    If evaluation_count is low, use self-reported experience_years as a bootstrap signal.
    """
    if evaluation_count < 10:
        # Fall back to self-reported experience when code history is short
        if experience_years >= 5:
            return "advanced"
        if experience_years >= 2:
            return "intermediate"
        return "beginner"
    if avg_score >= 75 and evaluation_count >= 50:
        return "advanced"
    if avg_score >= 50:
        return "intermediate"
    return "beginner"


def build_developer_history_section(profile: dict) -> str:
    """
    Convert a developer profile dict (as returned by DjangoClient.get_adaptive_profile)
    into a text section to prepend to the LLM prompt.

    Expected profile shape:
    {
        "level": "intermediate",
        "avg_score": 62.5,
        "evaluation_count": 18,
        "strengths": ["clean_code", "testing"],
        "weaknesses": ["error_handling", "security"],
        "frequent_patterns": [
            {"pattern_key": "error_handling:warning", "count": 5, "last_seen": "..."},
        ],
        "recommendations": ["..."],
        # Optional self-reported fields from UserDevProfile:
        "job_role": "fullstack",
        "primary_language": "Python",
        "current_goal": "become_senior",
        "learning_style": "examples",
        "want_to_improve": "testing",
        "enjoy_most": "backend_logic",
        "experience_years": 3.0,
    }
    Returns empty string if profile is None / empty (graceful degradation).
    """
    if not profile:
        return ""

    level = profile.get("level", "intermediate")
    strengths = profile.get("strengths", [])
    weaknesses = profile.get("weaknesses", [])
    frequent_patterns = profile.get("frequent_patterns", [])
    avg_score = profile.get("avg_score", 50)
    eval_count = profile.get("evaluation_count", 0)

    # Self-reported context
    job_role = profile.get("job_role", "")
    primary_language = profile.get("primary_language", "")
    experience_years = profile.get("experience_years")
    current_goal = profile.get("current_goal", "")
    learning_style = profile.get("learning_style", "")
    want_to_improve = profile.get("want_to_improve", "")

    lines: list[str] = [
        "═══ DEVELOPER PROFILE (use this context to personalise your review) ═══",
        f"Level: {level}  |  Avg score: {avg_score:.0f}/100  |  Reviews processed: {eval_count}",
    ]

    # Self-reported background (only if available)
    background_parts = []
    if job_role:
        background_parts.append(f"Role: {job_role.replace('_', ' ')}")
    if primary_language:
        background_parts.append(f"Main language: {primary_language}")
    if experience_years is not None:
        background_parts.append(f"Experience: {experience_years}y")
    if background_parts:
        lines.append("  ".join(background_parts))

    if strengths:
        lines.append(f"Strengths: {', '.join(strengths[:5])}")

    if weaknesses:
        lines.append(
            f"Weak areas (pay extra attention here): {', '.join(weaknesses[:5])}"
        )

    # G10: Per-category skill levels (if available in profile)
    category_scores = profile.get("category_scores", {})
    if category_scores:
        cat_levels = []
        for cat, score in sorted(category_scores.items(), key=lambda x: x[1]):
            if score >= 75:
                cat_level = "advanced"
            elif score >= 50:
                cat_level = "intermediate"
            else:
                cat_level = "beginner"
            cat_levels.append(f"  {cat}: {cat_level} ({score:.0f}/100)")
        lines.append("Per-category skill levels:")
        lines.extend(cat_levels)

    if want_to_improve:
        lines.append(f"Self-reported improvement goal: {want_to_improve.replace('_', ' ')}")

    if frequent_patterns:
        # G6: Sort patterns by recency-weighted score (recent patterns ranked higher)
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)

        def _recency_score(p):
            count = p.get("count", 0)
            last_seen = p.get("last_seen", "")
            days_ago = 30  # default if no date
            if last_seen:
                try:
                    from dateutil.parser import parse as parse_date
                    dt = parse_date(last_seen)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    days_ago = max(1, (now - dt).days)
                except Exception:
                    pass
            # Higher score = more important: frequency * recency_weight
            recency_weight = 30.0 / days_ago  # recent = higher weight
            return count * recency_weight

        sorted_patterns = sorted(frequent_patterns, key=_recency_score, reverse=True)

        pat_summaries = []
        for p in sorted_patterns[:5]:
            key = p.get("pattern_key", "")
            count = p.get("count", 0)
            display = key.split(":")[0].replace("_", " ")
            rec = PATTERN_RECOMMENDATIONS.get(key.split(":")[0], "")
            last_seen = p.get("last_seen", "")
            entry = f"  • {display} (seen {count}×)"
            if last_seen:
                entry += f" [last: {last_seen[:10]}]"
            if rec:
                entry += f" — {rec}"
            pat_summaries.append(entry)
        lines.append("Recurring issues to watch for:")
        lines.extend(pat_summaries)

    # Level-specific tone instruction
    tone = LEVEL_INSTRUCTIONS.get(level, LEVEL_INSTRUCTIONS["intermediate"])
    lines.append(f"\nReview tone: {tone}")

    # Learning-style instruction
    if learning_style:
        style_note = LEARNING_STYLE_INSTRUCTIONS.get(learning_style, "")
        if style_note:
            lines.append(f"Presentation style: {style_note}")

    # Goal context
    if current_goal:
        goal_note = GOAL_CONTEXT.get(current_goal, "")
        if goal_note:
            lines.append(f"Goal context: {goal_note}")

    lines.append("═══════════════════════════════════════════════════════════════")

    return "\n".join(lines)


def enrich_context_files(context_files: list[dict], profile: dict) -> list[dict]:
    """
    Prepend the developer history section to context_files so the LLM adapter
    receives it alongside related file contents.
    Idempotent – only adds it once even if called multiple times.
    """
    history = build_developer_history_section(profile)
    if not history:
        return context_files

    # Avoid duplicating if already present
    if any(f.get("path") == "__developer_profile__" for f in context_files):
        return context_files

    return [{"path": "__developer_profile__", "content": history}] + list(context_files)


def build_profile_from_skill_data(skill_categories: list[dict], evaluation_count: int) -> dict:
    """
    Build a profile dict from Django's /api/skills/profile/ response format.
    Used as fallback when the richer adaptive endpoint is unavailable.
    """
    strengths: list[str] = []
    weaknesses: list[str] = []
    total_score = 0.0
    skill_count = 0

    for cat in skill_categories:
        for skill in cat.get("skills", []):
            score = skill.get("score", 50)
            slug = skill.get("slug") or skill.get("displayName", "").lower().replace(" ", "_")
            total_score += score
            skill_count += 1
            if score >= STRENGTH_THRESHOLD:
                strengths.append(slug)
            elif score <= WEAKNESS_THRESHOLD:
                weaknesses.append(slug)

    avg_score = (total_score / skill_count) if skill_count else 50.0
    level = compute_level(avg_score, evaluation_count)

    return {
        "level": level,
        "avg_score": avg_score,
        "evaluation_count": evaluation_count,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "frequent_patterns": [],
        "recommendations": [],
    }
