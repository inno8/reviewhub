"""
Migration: add CohortTeacher — explicit teacher-to-cohort membership.

Complements CohortMembership (student-to-cohort) so the school admin can
assign teachers to a cohort independently of Course creation.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0005_shared_repo_contributors"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CohortTeacher",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "cohort",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teacher_assignments",
                        to="grading.cohort",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        help_text="Must have role=TEACHER.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cohort_teacher_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "grading_cohort_teachers",
                "ordering": ["added_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="cohortteacher",
            constraint=models.UniqueConstraint(
                fields=["cohort", "teacher"],
                name="uniq_cohort_teacher",
            ),
        ),
    ]
