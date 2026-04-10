"""
Backfill SkillMetric records from existing FindingSkill rows.

Useful when evaluations were ingested with author=None (unmatched git email),
but the user has since linked their git identity via GitProviderConnection or
ProjectMember.git_email / git_username.

Run:
    python manage.py backfill_skill_metrics
    python manage.py backfill_skill_metrics --dry-run
    python manage.py backfill_skill_metrics --user-email demo@reviewhub.dev
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

from evaluations.models import Evaluation, FindingSkill
from skills.models import SkillMetric
from users.models import User


class Command(BaseCommand):
    help = 'Backfill SkillMetric from existing FindingSkill rows (for users matched via git identity)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print what would change without saving')
        parser.add_argument('--user-email', type=str, help='Only process this user')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_email = options.get('user_email')

        users = User.objects.all()
        if target_email:
            users = users.filter(email__iexact=target_email)

        total_created = 0
        total_updated = 0

        for user in users:
            evals = Evaluation.objects.for_user(user)
            if not evals.exists():
                continue

            # Aggregate FindingSkill impact grouped by (project, skill)
            fs_qs = FindingSkill.objects.filter(
                finding__evaluation__in=evals,
            ).select_related('skill', 'finding', 'finding__evaluation__project', 'finding__evaluation')

            # bucket: (project_id, skill_id) -> {issues, fixed, impact_sum, project, skill, first_at, last_at}
            buckets: dict = defaultdict(lambda: {
                'issues': 0, 'fixed': 0, 'impact_sum': 0.0,
                'project': None, 'skill': None,
                'first_at': None, 'last_at': None,
            })

            for fs in fs_qs:
                proj = fs.finding.evaluation.project
                skill = fs.skill
                key = (proj.id, skill.id)
                b = buckets[key]
                b['project'] = proj
                b['skill'] = skill
                b['issues'] += 1
                if fs.finding.is_fixed:
                    b['fixed'] += 1
                b['impact_sum'] += fs.impact_score
                eval_ts = fs.finding.evaluation.created_at
                if b['first_at'] is None or eval_ts < b['first_at']:
                    b['first_at'] = eval_ts
                if b['last_at'] is None or eval_ts > b['last_at']:
                    b['last_at'] = eval_ts

            for (proj_id, skill_id), b in buckets.items():
                score = max(5.0, 100.0 - b['impact_sum'])

                if dry_run:
                    existing = SkillMetric.objects.filter(user=user, project=b['project'], skill=b['skill']).first()
                    action = 'UPDATE' if existing else 'CREATE'
                    self.stdout.write(
                        f"  [{action}] {user.email} | {b['project'].name} | {b['skill'].name} "
                        f"issues={b['issues']} score={round(score,1)}"
                    )
                    continue

                metric, created = SkillMetric.objects.get_or_create(
                    user=user,
                    project=b['project'],
                    skill=b['skill'],
                    defaults={
                        'score': score,
                        'issue_count': b['issues'],
                        'fixed_count': b['fixed'],
                        'first_evaluated_at': b['first_at'],
                        'last_evaluated_at': b['last_at'],
                    }
                )
                if created:
                    total_created += 1
                else:
                    # Only update if we have more data (don't overwrite higher scores from live ingest)
                    if b['issues'] > metric.issue_count:
                        metric.score = min(metric.score, score)
                        metric.issue_count = b['issues']
                        metric.fixed_count = b['fixed']
                        if b['first_at'] and (metric.first_evaluated_at is None or b['first_at'] < metric.first_evaluated_at):
                            metric.first_evaluated_at = b['first_at']
                        if b['last_at'] and (metric.last_evaluated_at is None or b['last_at'] > metric.last_evaluated_at):
                            metric.last_evaluated_at = b['last_at']
                        metric.save()
                        total_updated += 1

            if not dry_run:
                self.stdout.write(f"  {user.email}: processed {len(buckets)} (project, skill) pairs")

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run — no changes saved.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nDone! Created {total_created}, updated {total_updated} SkillMetric records.'
            ))
