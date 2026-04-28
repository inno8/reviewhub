"""
Migration: enforce one course per teacher per cohort.

A teacher may teach many cohorts but only holds ONE course inside any given
cohort. This is a partial unique constraint (NULL cohort is exempt) so legacy
courses without a cohort assignment are unaffected.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0006_cohort_teacher"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="course",
            constraint=models.UniqueConstraint(
                condition=models.Q(cohort__isnull=False, archived_at__isnull=True),
                fields=["cohort", "owner"],
                name="uniq_course_cohort_owner",
            ),
        ),
    ]
