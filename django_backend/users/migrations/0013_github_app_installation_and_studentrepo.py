"""
Adds the GitHub App installation tracking tables. Created during the
PAT → GitHub App auth migration (Workstream: GitHub App, Day 1 of 2).

Two new tables:

  github_installations
    One row per GitHub App install. Created in /api/github/install-callback,
    updated by the `installation` webhook events (suspend / unsuspend /
    delete). The installation_id is the only thing we need to mint
    short-lived installation tokens via the App's private key.

  student_repos
    One row per repo the student has authorized inside an installation.
    Synced from GitHub on install + via `installation_repositories`
    webhook events. The repo's commits + PRs are the access boundary
    for the LEERA App.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_add_teacher_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GitHubInstallation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'installation_id',
                    models.BigIntegerField(
                        unique=True,
                        help_text="GitHub's installation id (stable identifier).",
                    ),
                ),
                ('github_account_id', models.BigIntegerField()),
                ('github_account_login', models.CharField(max_length=200)),
                (
                    'github_account_type',
                    models.CharField(
                        choices=[('User', 'User'), ('Organization', 'Organization')],
                        default='User',
                        help_text='User = personal account; Organization = a GitHub org.',
                        max_length=20,
                    ),
                ),
                (
                    'repository_selection',
                    models.CharField(
                        choices=[
                            ('all', 'All repositories'),
                            ('selected', 'Selected repositories'),
                        ],
                        default='selected',
                        max_length=20,
                    ),
                ),
                ('suspended_at', models.DateTimeField(blank=True, null=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        help_text='The LEERA user who completed the install flow.',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='github_installations',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'github_installations',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='githubinstallation',
            index=models.Index(fields=['user'], name='github_inst_user_id_idx'),
        ),
        migrations.AddIndex(
            model_name='githubinstallation',
            index=models.Index(fields=['github_account_id'], name='github_inst_acct_id_idx'),
        ),
        migrations.CreateModel(
            name='StudentRepo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('github_repo_id', models.BigIntegerField()),
                (
                    'full_name',
                    models.CharField(
                        help_text='e.g. "ahmed-b/student-portfolio"',
                        max_length=200,
                    ),
                ),
                ('default_branch', models.CharField(default='main', max_length=200)),
                ('is_private', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('removed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'installation',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='repos',
                        to='users.githubinstallation',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='student_repos',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'student_repos',
                'ordering': ['full_name'],
                'unique_together': {('installation', 'github_repo_id')},
            },
        ),
        migrations.AddIndex(
            model_name='studentrepo',
            index=models.Index(fields=['user', 'is_active'], name='student_repo_user_active_idx'),
        ),
        migrations.AddIndex(
            model_name='studentrepo',
            index=models.Index(fields=['github_repo_id'], name='student_repo_gh_id_idx'),
        ),
    ]
