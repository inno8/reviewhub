# Generated for Scope B2 — Nakijken Copilot v1 hybrid Layer 1 (shadow mode)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0007_production_hardening'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeterministicFinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('runner', models.CharField(
                    choices=[('ruff', 'ruff (Python)'), ('eslint', 'ESLint (JS/TS)')],
                    help_text='Which deterministic runner produced this finding.',
                    max_length=20,
                )),
                ('rule_id', models.CharField(
                    help_text="Runner-native rule id, e.g. 'E501', 'no-unused-vars'.",
                    max_length=64,
                )),
                ('message', models.TextField()),
                ('severity', models.CharField(
                    choices=[
                        ('critical', 'Critical'),
                        ('warning', 'Warning'),
                        ('info', 'Info'),
                        ('suggestion', 'Suggestion'),
                    ],
                    default='warning',
                    max_length=20,
                )),
                ('file_path', models.CharField(max_length=500)),
                ('line_start', models.PositiveIntegerField()),
                ('line_end', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('evaluation', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='deterministic_findings',
                    to='evaluations.evaluation',
                )),
                ('matched_llm_finding', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='matched_deterministic_findings',
                    to='evaluations.finding',
                )),
            ],
            options={
                'db_table': 'deterministic_findings',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['evaluation', 'runner'], name='determinist_evaluat_393fe8_idx'),
                    models.Index(fields=['runner', 'rule_id'], name='determinist_runner_5c90e6_idx'),
                ],
            },
        ),
    ]
