"""
Management command to generate weekly digest notifications for developers.
Run weekly via cron or scheduler: python manage.py send_weekly_digest

Aggregates the past 7 days of code review activity per developer and creates
a 'weekly_summary' notification with metrics, trends, and action items.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Q
from django.utils import timezone

from evaluations.models import Evaluation, Finding, Pattern
from notifications.models import Notification
from skills.models import SkillMetric

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate weekly digest notifications for all active developers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='Number of days to look back (default: 7)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print digests without creating notifications',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        since = timezone.now() - timedelta(days=days)

        # Find developers who had evaluations in the period
        developers = (
            User.objects
            .filter(role='developer')
            .filter(
                Q(evaluations__created_at__gte=since)
                | Q(notifications__type='new_finding', notifications__created_at__gte=since)
            )
            .distinct()
        )

        created = 0
        skipped = 0

        for user in developers:
            # Skip if already sent a digest this week
            existing = Notification.objects.filter(
                user=user,
                type='weekly_summary',
                created_at__gte=since,
            ).exists()
            if existing:
                skipped += 1
                continue

            digest = self._build_digest(user, since)
            if not digest:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"\n--- {user.email} ---")
                self.stdout.write(f"  Title: {digest['title']}")
                self.stdout.write(f"  Message: {digest['message']}")
                self.stdout.write(f"  Data: {digest['data']}")
            else:
                Notification.objects.create(
                    user=user,
                    type='weekly_summary',
                    title=digest['title'],
                    message=digest['message'],
                    data=digest['data'],
                )
                created += 1

        verb = 'Would create' if dry_run else 'Created'
        count = created if not dry_run else created
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {created} weekly digest(s). Skipped {skipped} developer(s).'
        ))

    def _build_digest(self, user, since):
        """Build a weekly digest for a single developer."""
        evaluations = Evaluation.objects.filter(
            author=user,
            created_at__gte=since,
        )
        if not evaluations.exists():
            return None

        eval_count = evaluations.count()
        scores = [e.overall_score for e in evaluations if e.overall_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Findings stats
        findings = Finding.objects.filter(
            evaluation__in=evaluations,
        )
        total_findings = findings.count()
        critical_count = findings.filter(severity__in=['critical', 'error']).count()
        fixed_count = findings.filter(is_fixed=True).count()

        # Score trend: compare this week to previous week
        prev_start = since - timedelta(days=7)
        prev_evals = Evaluation.objects.filter(
            author=user,
            created_at__gte=prev_start,
            created_at__lt=since,
        )
        prev_scores = [e.overall_score for e in prev_evals if e.overall_score is not None]
        prev_avg = sum(prev_scores) / len(prev_scores) if prev_scores else None

        if prev_avg is not None and avg_score:
            delta = avg_score - prev_avg
            if delta > 2:
                trend_text = f"up {delta:.1f} pts from last week"
                trend = 'improving'
            elif delta < -2:
                trend_text = f"down {abs(delta):.1f} pts from last week"
                trend = 'declining'
            else:
                trend_text = "stable compared to last week"
                trend = 'stable'
        else:
            trend_text = "first week tracked"
            trend = 'new'

        # Patterns
        new_patterns = Pattern.objects.filter(
            user=user,
            first_seen__gte=since,
            is_resolved=False,
        ).count()
        resolved_patterns = Pattern.objects.filter(
            user=user,
            is_resolved=True,
            last_seen__gte=since,
        ).count()

        # Skills improved
        improved_skills = SkillMetric.objects.filter(
            user=user,
            score__gt=0,
        ).filter(
            Q(previous_score__isnull=False),
            score__gt=F('previous_score'),
        ).count() if hasattr(SkillMetric, 'previous_score') else 0

        # Top issue category
        top_category = (
            findings
            .exclude(evaluation__isnull=True)
            .values('evaluation__commit_sha')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )

        # Build message
        lines = [
            f"This week: {eval_count} commit{'s' if eval_count != 1 else ''} reviewed, "
            f"avg score {avg_score:.0f}/100 ({trend_text}).",
        ]
        if total_findings:
            lines.append(
                f"Found {total_findings} issue{'s' if total_findings != 1 else ''}"
                f"{f', {critical_count} critical' if critical_count else ''}."
                f"{f' Fixed {fixed_count}!' if fixed_count else ''}"
            )
        if new_patterns:
            lines.append(f"{new_patterns} new pattern{'s' if new_patterns != 1 else ''} detected.")
        if resolved_patterns:
            lines.append(f"{resolved_patterns} pattern{'s' if resolved_patterns != 1 else ''} resolved!")

        # Action items
        actions = []
        if critical_count:
            actions.append("Review critical findings")
        if new_patterns:
            actions.append("Check new patterns on Skills page")
        if fixed_count == 0 and total_findings > 0:
            actions.append("Try Fix & Learn on your findings")

        title = f"Weekly Digest: {avg_score:.0f}/100 avg score ({trend_text})"

        return {
            'title': title[:255],
            'message': ' '.join(lines),
            'data': {
                'period_days': (timezone.now() - since).days,
                'eval_count': eval_count,
                'avg_score': round(avg_score, 1),
                'total_findings': total_findings,
                'critical_count': critical_count,
                'fixed_count': fixed_count,
                'trend': trend,
                'trend_text': trend_text,
                'new_patterns': new_patterns,
                'resolved_patterns': resolved_patterns,
                'actions': actions,
            },
        }
