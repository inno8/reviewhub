# Generated for Leera Nakijken Copilot v1.
#
# Adds a nullable FK from skills.SkillObservation to grading.GradingSession
# so the rubric-grading flow can tag each observation with its source session
# and bind_rubric_to_observations can be idempotent on re-draft.
#
# Purely additive migration: nullable FK, on_delete=SET_NULL so deleting a
# GradingSession leaves the (user, skill, observation) historical record
# intact.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0007_course_unique_teacher_per_cohort'),
        ('skills', '0004_skillmetric_bayesian_score_skillmetric_confidence_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillobservation',
            name='grading_session',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='skill_observations',
                to='grading.gradingsession',
            ),
        ),
    ]
