"""
Batch Processing Services - Profile building and aggregation.
"""
from django.db.models import Avg
from django.utils import timezone


def build_profile_from_batch(user, batch_job):
    """
    Aggregate evaluations and skill metrics into a DeveloperProfile.
    Called automatically when a batch job completes.
    """
    from evaluations.models import Evaluation, Pattern
    from skills.models import SkillMetric
    from notifications.models import Notification
    from .models import DeveloperProfile

    # Get evaluations for this user+project (created during batch)
    evaluations = Evaluation.objects.filter(
        author=user,
        project=batch_job.project,
    ).order_by('commit_timestamp')

    if not evaluations.exists():
        return None

    # Overall score from evaluation averages
    scores = [e.overall_score for e in evaluations if e.overall_score is not None]
    overall_score = sum(scores) / len(scores) if scores else 50.0

    # Score history for trend calculation
    score_history = []
    for e in evaluations:
        if e.overall_score is not None and e.commit_timestamp:
            score_history.append({
                "date": e.commit_timestamp.strftime("%Y-%m-%d"),
                "score": float(e.overall_score),
            })

    # Strengths and weaknesses from SkillMetric
    metrics = SkillMetric.objects.filter(
        user=user,
        project=batch_job.project,
    ).select_related('skill').order_by('score')

    weaknesses = [m.skill.id for m in metrics if m.score < 50][:5]
    strengths = [m.skill.id for m in metrics.order_by('-score') if m.score > 75][:5]

    # Top patterns
    patterns = Pattern.objects.filter(
        user=user,
        project=batch_job.project,
    ).order_by('-frequency')[:10]

    top_patterns = [
        {"type": p.pattern_type, "key": p.pattern_key, "frequency": p.frequency}
        for p in patterns
    ]

    # Total findings
    total_findings = sum(e.finding_count for e in evaluations)

    # Date range
    first_eval = evaluations.first()
    last_eval = evaluations.last()

    # Create or update profile
    profile, _ = DeveloperProfile.objects.update_or_create(
        user=user,
        defaults={
            "batch_job": batch_job,
            "overall_score": overall_score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "top_patterns": top_patterns,
            "score_history": score_history,
            "commits_analyzed": batch_job.processed_commits,
            "total_findings": total_findings,
            "first_commit_date": (
                first_eval.commit_timestamp.date()
                if first_eval and first_eval.commit_timestamp else None
            ),
            "last_commit_date": (
                last_eval.commit_timestamp.date()
                if last_eval and last_eval.commit_timestamp else None
            ),
        }
    )

    # Calculate level and trend
    profile.level = profile.calculate_level()
    profile.trend = profile.calculate_trend()
    profile.save()

    # Create summary notification
    Notification.objects.create(
        user=user,
        type='batch_summary',
        title='Batch Analysis Complete',
        message=(
            f"Analyzed {batch_job.processed_commits} commits from "
            f"{batch_job.repo_url.split('/')[-1]}. "
            f"Found {total_findings} issues. "
            f"Your level: {profile.get_level_display()}."
        ),
        data={
            "batch_job_id": batch_job.id,
            "findings_count": total_findings,
            "overall_score": float(profile.overall_score),
            "level": profile.level,
            "trend": profile.trend,
        }
    )

    return profile
