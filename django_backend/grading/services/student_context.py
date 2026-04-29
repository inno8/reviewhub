"""
Build the per-student context that gets injected into the rubric-grading
LLM prompt.

The ai-engine `_build_user_prompt` function already has a placeholder
"STUDENT CONTEXT" block (ai_engine/app/api/grading.py:205-210) that
JSON-serializes whatever dict Django passes as `context=`. Until now,
Django passed `context={}` so the block was empty in every grading
session and the AI's draft was generic — no idea who the student was,
their level, what they're working on, or what mistakes they keep making.

This module collects the student's full calibration footprint:

  - Self-reported profile from the onboarding questionnaire
    (UserDevProfile)
  - Bayesian skill scores per category (SkillMetric — seeded from
    self_scores, updated from evidence over time)
  - Active recurring error patterns (Pattern — what they keep getting
    wrong; the LLM should call repeats out gently rather than treat
    them like first-time observations)
  - Recent proof state (LearningProof — what they've demonstrably
    learned vs relapsed on)

The dict is kept compact (target <1500 chars JSON-serialized — the
ai-engine truncates beyond that) and identity-free. No name, email,
GitHub handle, or other PII goes through to the LLM via this path.
The student_id field is included as an opaque integer for the LLM
to reference without leaking who the student is.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

User = get_user_model()


# Maximum number of items in each list-shaped section. Trimming aggressively
# to stay under the 1500-char prompt-context budget; recent + most-frequent
# is what the LLM needs, not the long tail.
_MAX_SKILL_SCORES = 8        # full set of categories per SkillCategory model
_MAX_ACTIVE_PATTERNS = 5     # top recurring errors by frequency
_MAX_LEARNING_PROOFS = 5     # most recent proof events


def build_student_context(student, project_id: int | None = None) -> dict[str, Any]:
    """
    Assemble a compact context dict for the LLM prompt.

    Args:
        student: the User the grading session is for (Submission.student)
        project_id: optional grading.Project id to scope SkillMetric +
            Pattern queries; None falls back to org-wide aggregates.
            Pass `submission.course.project_id` when available so the
            metrics reflect the assignment's project, not unrelated work.

    Returns:
        dict shaped for the prompt template. Empty dict if the student
        has no calibration data yet (no questionnaire submitted, no
        observations recorded). The grader treats empty as "generic
        student" and falls back to vanilla rubric scoring.
    """
    out: dict[str, Any] = {}

    profile = _profile_section(student)
    if profile:
        out['profile'] = profile

    skill_scores = _skill_scores_section(student, project_id)
    if skill_scores:
        out['skill_scores'] = skill_scores

    patterns = _active_patterns_section(student, project_id)
    if patterns:
        out['active_patterns'] = patterns

    proofs = _learning_proofs_section(student)
    if proofs:
        out['learning_proofs'] = proofs

    return out


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────

def _profile_section(student) -> dict[str, Any] | None:
    """The questionnaire answers. Returns None if no profile saved."""
    try:
        # UserDevProfile is OneToOne with User via related_name='dev_profile'
        # (users/models.py UserDevProfile.user OneToOneField).
        profile = student.dev_profile
    except Exception:
        # OneToOne lookup raises RelatedObjectDoesNotExist when missing.
        # `except Exception` catches it without importing the class.
        return None

    if not profile:
        return None

    # Compact projection — only fields that meaningfully shape the LLM's
    # tone and depth. Skip free-text proud_code/struggled_code (too long
    # for the prompt budget; surfaced separately in deeper analysis).
    return {
        'role': profile.job_role or None,
        'years': profile.experience_years if profile.experience_years is not None else None,
        'primary_lang': profile.primary_language or None,
        'other_langs': list(profile.other_languages or [])[:5],  # cap list length
        'current_goal': profile.current_goal or None,
        'learning_style': profile.learning_style or None,
        'wants_to_improve': profile.want_to_improve or None,
        'focus_first': profile.focus_first or None,
    }


def _skill_scores_section(student, project_id: int | None) -> dict[str, dict[str, Any]]:
    """
    Top-N skill scores by confidence. Maps skill slug → {score, confidence}.

    Score 0-100 (Bayesian, evidence-weighted). Confidence 0-1 — the LLM
    should weight low-confidence scores accordingly (early in the
    semester, confidence is low and self-reported scores dominate).
    """
    try:
        from skills.models import SkillMetric
    except ImportError:
        return {}

    qs = SkillMetric.objects.filter(user=student).select_related('skill')
    if project_id is not None:
        qs = qs.filter(project_id=project_id)

    # Order by confidence desc so high-evidence categories surface first
    # — those carry more weight in the LLM's level assessment.
    qs = qs.order_by('-confidence', '-bayesian_score')[:_MAX_SKILL_SCORES]

    out: dict[str, dict[str, Any]] = {}
    for m in qs:
        slug = getattr(m.skill, 'slug', None) or getattr(m.skill, 'name', '?')
        out[slug] = {
            'score': round(m.bayesian_score, 1),
            'conf': round(m.confidence, 2),
        }
    return out


def _active_patterns_section(student, project_id: int | None) -> list[dict[str, Any]]:
    """
    Top unresolved recurring error patterns. The LLM should call repeats
    out softly ("we've seen this before; let's tackle the root cause")
    rather than treating each occurrence as first-time observation.
    """
    try:
        from evaluations.models import Pattern
    except ImportError:
        return []

    qs = Pattern.objects.filter(user=student, is_resolved=False)
    if project_id is not None:
        qs = qs.filter(project_id=project_id)

    qs = qs.order_by('-frequency', '-last_seen')[:_MAX_ACTIVE_PATTERNS]

    return [
        {
            'type': p.pattern_type,
            'key': p.pattern_key[:60],   # truncate long keys
            'count': p.frequency,
        }
        for p in qs
    ]


def _learning_proofs_section(student) -> list[dict[str, Any]]:
    """
    Recent proof state — what's PROVEN (learned), RELAPSED (regressed
    after teaching), or REINFORCED (repeated correct application).
    """
    try:
        from skills.models import LearningProof
    except ImportError:
        return []

    qs = (
        LearningProof.objects.filter(user=student)
        .filter(status__in=['PROVEN', 'RELAPSED', 'REINFORCED'])
        .select_related('skill')
        .order_by('-updated_at')[:_MAX_LEARNING_PROOFS]
    )

    return [
        {
            'skill': getattr(p.skill, 'slug', None) or getattr(p.skill, 'name', '?'),
            'state': p.status,
            # issue_type may not exist on every proof; use getattr for safety
            'issue': getattr(p, 'issue_type', None) or None,
        }
        for p in qs
    ]
