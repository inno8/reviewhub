# v1.1 task F4 — add phpcs + phpstan to DeterministicFinding.runner choices.
#
# ai_engine has shipped both runners for a while (see
# ai_engine/app/services/deterministic/phpcs_runner.py and
# phpstan_runner.py), but Django's choices list only allowed 'ruff' and
# 'eslint'. PHP findings hit the serializer with
# runner='phpcs' / runner='phpstan' and were silently dropped.
#
# Choices-only migration. No database column type change (max_length=20
# already accommodates both new values). Existing rows untouched.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0008_deterministic_finding'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deterministicfinding',
            name='runner',
            field=models.CharField(
                choices=[
                    ('ruff', 'ruff (Python)'),
                    ('eslint', 'ESLint (JS/TS)'),
                    ('phpcs', 'phpcs (PHP / PSR-12)'),
                    ('phpstan', 'phpstan (PHP)'),
                ],
                help_text='Which deterministic runner produced this finding.',
                max_length=20,
            ),
        ),
    ]
