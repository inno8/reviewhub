"""
Composite developer level calculator (v2 — Bayesian Learning Algorithm).

Uses evidence-based scoring across multiple signals:
- Bayesian skill scores (complexity-weighted, confidence-gated)
- Growth trajectory (improvement trend, severity graduation)
- Behavioral proof rate (Fix & Learn proven vs relapsed)
- Complexity progression (tackling harder problems over time)
- Decision quality (appropriate architectural choices)
- Fix engagement (fix rate, recovery speed)
- Skill breadth (range of skills demonstrated)

Levels: novice (0-15), beginner (15-30), competent (30-50),
        proficient (50-70), expert (70-85), master (85-100)

See docs/LEARNING_ALGORITHM.md for full specification.
"""
from .models import (
    LEVEL_THRESHOLDS,
    MIN_EVALS_FOR_LEVEL,
    CONFIDENCE_PRELIMINARY,
)


def calculate_developer_level(
    avg_bayesian_score: float = 50,
    improvement_pct: float = 0,
    fix_rate: float = 0,
    patterns_resolved: int = 0,
    patterns_total: int = 0,
    understanding_got_it: int = 0,
    understanding_total: int = 0,
    experience_years: float = 0,
    # ── New v2 signals ──
    proven_concepts: int = 0,
    relapsed_concepts: int = 0,
    avg_complexity: float = 0.5,
    total_evaluations: int = 0,
    avg_confidence: float = 0.0,
    decision_appropriate: int = 0,
    decision_total: int = 0,
    skills_with_data: int = 0,
    total_skills: int = 32,
) -> dict:
    """
    Calculate composite developer level from multiple signals.

    Returns:
        {
            'level': str,
            'composite_score': float (0-100),
            'confidence': str ('insufficient'|'preliminary'|'developing'|'established'|'verified'),
            'min_evals_met': bool,
            'breakdown': { factor: { score, weight, weighted } },
        }
    """
    # ── 1. Code quality (Bayesian avg, already complexity-weighted) ── 25%
    quality_score = min(100, max(0, avg_bayesian_score))

    # ── 2. Growth trajectory ── 20%
    # Map improvement from -50..+50 to 0..100
    improvement_score = min(100, max(0, improvement_pct + 50))

    # ── 3. Behavioral proof rate ── 15%
    # What % of taught concepts were proven by future behavior?
    proof_total = proven_concepts + relapsed_concepts
    if proof_total > 0:
        proof_score = (proven_concepts / proof_total) * 100
    else:
        proof_score = 50  # neutral if no proofs yet

    # ── 4. Fix engagement ── 10%
    fix_score = min(100, max(0, fix_rate))

    # ── 5. Complexity progression ── 10%
    # avg_complexity 0.0-1.0 → 0-100
    complexity_score = min(100, max(0, avg_complexity * 100))

    # ── 6. Decision quality ── 10%
    if decision_total > 0:
        decision_score = (decision_appropriate / decision_total) * 100
    else:
        decision_score = 50  # neutral if no decision data

    # ── 7. Skill breadth ── 5%
    if total_skills > 0:
        breadth_score = min(100, (skills_with_data / total_skills) * 200)
        # 50% coverage = 100 score (covering half the skills is very broad)
    else:
        breadth_score = 0

    # ── 8. Pattern resolution ── 5%
    if patterns_total > 0:
        pattern_score = (patterns_resolved / patterns_total) * 100
    else:
        pattern_score = 50

    # Weighted composite
    weights = {
        'code_quality':      0.25,
        'improvement':       0.20,
        'behavioral_proof':  0.15,
        'fix_engagement':    0.10,
        'complexity':        0.10,
        'decision_quality':  0.10,
        'breadth':           0.05,
        'patterns':          0.05,
    }

    scores = {
        'code_quality':      quality_score,
        'improvement':       improvement_score,
        'behavioral_proof':  proof_score,
        'fix_engagement':    fix_score,
        'complexity':        complexity_score,
        'decision_quality':  decision_score,
        'breadth':           breadth_score,
        'patterns':          pattern_score,
    }

    composite = sum(scores[k] * weights[k] for k in weights)
    composite = round(composite, 1)

    # Map to level
    level = 'novice'
    for lvl, threshold in LEVEL_THRESHOLDS.items():
        if composite >= threshold:
            level = lvl
            break

    # Check minimum evaluation requirement
    min_evals = MIN_EVALS_FOR_LEVEL.get(level, 0)
    min_evals_met = total_evaluations >= min_evals
    if not min_evals_met:
        # Cap level at what the evaluation count supports
        for lvl, min_req in sorted(
            MIN_EVALS_FOR_LEVEL.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if total_evaluations >= min_req:
                level = lvl
                break
        else:
            level = 'novice'

    # Confidence label
    if avg_confidence >= 0.85:
        confidence_label = 'verified'
    elif avg_confidence >= 0.70:
        confidence_label = 'established'
    elif avg_confidence >= 0.40:
        confidence_label = 'developing'
    elif avg_confidence >= 0.15:
        confidence_label = 'preliminary'
    else:
        confidence_label = 'insufficient'

    breakdown = {}
    for k in weights:
        breakdown[k] = {
            'score': round(scores[k], 1),
            'weight': int(weights[k] * 100),
            'weighted': round(scores[k] * weights[k], 1),
        }

    return {
        'level': level,
        'composite_score': composite,
        'confidence': confidence_label,
        'min_evals_met': min_evals_met,
        'total_evaluations': total_evaluations,
        'breakdown': breakdown,
    }


def compute_level_for_user(user, project_id=None):
    """
    Compute composite level for a Django User, pulling data from all models.
    Uses the v2 Bayesian Learning Algorithm.
    """
    from evaluations.models import Evaluation, Finding, Pattern
    from skills.models import SkillMetric, SkillObservation, LearningProof
    from django.db.models import Avg, Count, Q

    # ── Evaluations ──
    evals = Evaluation.objects.for_user(user)
    if project_id:
        evals = evals.filter(project_id=project_id)

    total_evaluations = evals.count()
    avg_score = evals.aggregate(avg=Avg('overall_score'))['avg'] or 0

    # ── Findings & Fix rate ──
    finding_count = Finding.objects.filter(evaluation__in=evals).count()
    fixed_count = Finding.objects.filter(evaluation__in=evals, is_fixed=True).count()
    fix_rate = (fixed_count / finding_count * 100) if finding_count else 0

    # ── Improvement trend ──
    scores_list = [
        s for s in evals.order_by('created_at').values_list('overall_score', flat=True)
        if s is not None
    ]
    improvement_pct = 0
    if len(scores_list) >= 3:
        first_3 = sum(scores_list[:3]) / 3
        last_3 = sum(scores_list[-3:]) / 3
        improvement_pct = last_3 - first_3

    # ── Patterns ──
    pattern_qs = Pattern.objects.filter(user=user)
    if project_id:
        pattern_qs = pattern_qs.filter(project_id=project_id)
    patterns_total = pattern_qs.count()
    patterns_resolved = pattern_qs.filter(is_resolved=True).count()

    # ── Understanding (Fix & Learn) ──
    findings_with_understanding = Finding.objects.filter(
        evaluation__in=evals
    ).exclude(understanding_level='')
    understanding_total = findings_with_understanding.count()
    understanding_got_it = findings_with_understanding.filter(
        understanding_level='got_it'
    ).count()

    # ── Experience ──
    experience_years = 0
    try:
        if hasattr(user, 'dev_profile') and user.dev_profile:
            experience_years = user.dev_profile.experience_years or 0
    except Exception:
        pass

    # ── v2 Bayesian signals ──
    metrics_qs = SkillMetric.objects.filter(user=user)
    if project_id:
        metrics_qs = metrics_qs.filter(project_id=project_id)

    metrics_with_data = metrics_qs.filter(observation_count__gt=0)
    avg_bayesian = metrics_with_data.aggregate(
        avg=Avg('bayesian_score')
    )['avg'] or avg_score  # fallback to legacy score
    avg_confidence = metrics_with_data.aggregate(
        avg=Avg('confidence')
    )['avg'] or 0
    skills_with_data = metrics_with_data.count()

    # Proven/relapsed concepts
    proof_qs = LearningProof.objects.filter(user=user)
    if project_id:
        proof_qs = proof_qs.filter(
            finding__evaluation__project_id=project_id,
        )
    proven_concepts = proof_qs.filter(
        status__in=['proven', 'reinforced']
    ).count()
    relapsed_concepts = proof_qs.filter(status='relapsed').count()

    # Average complexity
    obs_qs = SkillObservation.objects.filter(user=user)
    if project_id:
        obs_qs = obs_qs.filter(project_id=project_id)
    avg_complexity = obs_qs.aggregate(
        avg=Avg('complexity_weight')
    )['avg'] or 0.5

    # Decision quality
    decision_agg = obs_qs.aggregate(
        appropriate=Count('id', filter=Q(decision_appropriate__gt=0)),
        total=Count('id', filter=Q(
            Q(decision_appropriate__gt=0) |
            Q(decision_suboptimal__gt=0) |
            Q(decision_poor__gt=0)
        )),
    )
    decision_appropriate = decision_agg['appropriate'] or 0
    decision_total = decision_agg['total'] or 0

    return calculate_developer_level(
        avg_bayesian_score=avg_bayesian,
        improvement_pct=improvement_pct,
        fix_rate=fix_rate,
        patterns_resolved=patterns_resolved,
        patterns_total=patterns_total,
        understanding_got_it=understanding_got_it,
        understanding_total=understanding_total,
        experience_years=experience_years,
        proven_concepts=proven_concepts,
        relapsed_concepts=relapsed_concepts,
        avg_complexity=avg_complexity,
        total_evaluations=total_evaluations,
        avg_confidence=avg_confidence,
        decision_appropriate=decision_appropriate,
        decision_total=decision_total,
        skills_with_data=skills_with_data,
    )
