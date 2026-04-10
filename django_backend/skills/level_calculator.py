"""
Composite developer level calculator.

Combines multiple signals to determine a developer's skill level:
- Average code quality score (30%)
- Improvement trend (20%)
- Fix rate (15%)
- Patterns resolved (15%)
- Understanding rate from Fix & Learn (10%)
- Experience years from profile (10%)

Levels: beginner (0-30), junior (30-50), intermediate (50-70), senior (70-85), expert (85-100)
"""


def calculate_developer_level(
    avg_score: float = 0,
    improvement_pct: float = 0,
    fix_rate: float = 0,
    patterns_resolved: int = 0,
    patterns_total: int = 0,
    understanding_got_it: int = 0,
    understanding_total: int = 0,
    experience_years: float = 0,
) -> dict:
    """
    Calculate composite developer level from multiple signals.

    Returns:
        {
            'level': 'beginner'|'junior'|'intermediate'|'senior'|'expert',
            'composite_score': float (0-100),
            'breakdown': { factor: { score, weight, weighted } },
        }
    """
    # 1. Code quality score (0-100) → weight 30%
    quality_score = min(100, max(0, avg_score))

    # 2. Improvement trend (map -50..+50 to 0..100) → weight 20%
    # Clamped: -50% or worse = 0, +50% or better = 100
    improvement_score = min(100, max(0, (improvement_pct + 50)))

    # 3. Fix rate (0-100%) → weight 15%
    fix_score = min(100, max(0, fix_rate))

    # 4. Patterns resolved ratio (0-100%) → weight 15%
    if patterns_total > 0:
        pattern_score = (patterns_resolved / patterns_total) * 100
    else:
        pattern_score = 50  # neutral if no patterns detected

    # 5. Understanding rate from Fix & Learn (0-100%) → weight 10%
    if understanding_total > 0:
        understanding_score = (understanding_got_it / understanding_total) * 100
    else:
        understanding_score = 50  # neutral if never tested

    # 6. Experience years (0-10+ mapped to 0-100) → weight 10%
    experience_score = min(100, (experience_years / 10) * 100)

    # Weighted composite
    weights = {
        'code_quality': 0.30,
        'improvement': 0.20,
        'fix_rate': 0.15,
        'patterns': 0.15,
        'understanding': 0.10,
        'experience': 0.10,
    }

    scores = {
        'code_quality': quality_score,
        'improvement': improvement_score,
        'fix_rate': fix_score,
        'patterns': pattern_score,
        'understanding': understanding_score,
        'experience': experience_score,
    }

    composite = sum(scores[k] * weights[k] for k in weights)
    composite = round(composite, 1)

    # Map to level
    if composite >= 85:
        level = 'expert'
    elif composite >= 70:
        level = 'senior'
    elif composite >= 50:
        level = 'intermediate'
    elif composite >= 30:
        level = 'junior'
    else:
        level = 'beginner'

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
        'breakdown': breakdown,
    }


def compute_level_for_user(user, project_id=None):
    """
    Compute composite level for a Django User, pulling data from all models.
    """
    from evaluations.models import Evaluation, Finding, Pattern
    from django.db.models import Avg

    # Evaluations
    evals = Evaluation.objects.for_user(user)
    if project_id:
        evals = evals.filter(project_id=project_id)

    avg_score = evals.aggregate(avg=Avg('overall_score'))['avg'] or 0
    finding_count = Finding.objects.filter(evaluation__in=evals).count()
    fixed_count = Finding.objects.filter(evaluation__in=evals, is_fixed=True).count()
    fix_rate = (fixed_count / finding_count * 100) if finding_count else 0

    # Improvement
    scores_list = [s for s in evals.order_by('created_at').values_list('overall_score', flat=True) if s is not None]
    improvement_pct = 0
    if len(scores_list) >= 3:
        first_3 = sum(scores_list[:3]) / 3
        last_3 = sum(scores_list[-3:]) / 3
        improvement_pct = last_3 - first_3

    # Patterns
    pattern_qs = Pattern.objects.filter(user=user)
    if project_id:
        pattern_qs = pattern_qs.filter(project_id=project_id)
    patterns_total = pattern_qs.count()
    patterns_resolved = pattern_qs.filter(is_resolved=True).count()

    # Understanding (Fix & Learn)
    findings_with_understanding = Finding.objects.filter(
        evaluation__in=evals
    ).exclude(understanding_level='')
    understanding_total = findings_with_understanding.count()
    understanding_got_it = findings_with_understanding.filter(understanding_level='got_it').count()

    # Experience
    experience_years = 0
    try:
        if hasattr(user, 'dev_profile') and user.dev_profile:
            experience_years = user.dev_profile.experience_years or 0
    except Exception:
        pass

    return calculate_developer_level(
        avg_score=avg_score,
        improvement_pct=improvement_pct,
        fix_rate=fix_rate,
        patterns_resolved=patterns_resolved,
        patterns_total=patterns_total,
        understanding_got_it=understanding_got_it,
        understanding_total=understanding_total,
        experience_years=experience_years,
    )
