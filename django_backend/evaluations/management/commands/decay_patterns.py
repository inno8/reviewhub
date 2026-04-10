"""
Management command to apply decay to pattern frequencies.
Run weekly via cron or scheduler: python manage.py decay_patterns
"""
from django.core.management.base import BaseCommand
from evaluations.models import Pattern


class Command(BaseCommand):
    help = 'Apply decay to all active patterns (run weekly)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rate', type=float, default=0.9,
            help='Decay rate (0-1). Default 0.9 means 10%% reduction per cycle.'
        )

    def handle(self, *args, **options):
        rate = options['rate']
        active_count = Pattern.objects.filter(is_resolved=False).count()
        Pattern.apply_global_decay(decay_rate=rate)
        resolved = Pattern.objects.filter(is_resolved=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Decayed {active_count} active patterns (rate={rate}). '
            f'{resolved} total resolved.'
        ))
