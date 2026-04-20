"""
Serializers for Workstream D — student intelligence endpoints.

These power the teacher-facing StudentSnapshotPanel + TeacherStudentProfileView
UIs (Workstream E). Kept in their own file so the existing grading serializers
(`grading/serializers.py`) are untouched.

Output is dict-shaped rather than model-backed: the data is aggregated from
several apps (grading, skills, evaluations) and shaped explicitly for the UI.
"""
from __future__ import annotations

from rest_framework import serializers


class _StudentRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()


class _CohortRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class _StudentWithCohortSerializer(_StudentRefSerializer):
    cohort = _CohortRefSerializer(allow_null=True)


class SkillRadarItemSerializer(serializers.Serializer):
    category = serializers.CharField()
    score = serializers.FloatField()
    confidence = serializers.FloatField()
    level_label = serializers.CharField(allow_null=True)
    trend = serializers.CharField()  # up / down / stable


class RecurringPatternSerializer(serializers.Serializer):
    pattern_key = serializers.CharField()
    pattern_type = serializers.CharField()
    frequency = serializers.IntegerField()
    last_seen_days_ago = serializers.IntegerField(allow_null=True)
    severity = serializers.CharField()  # warning / info — crude heuristic


class RecentActivitySerializer(serializers.Serializer):
    prs_last_30d = serializers.IntegerField()
    avg_bayesian_score = serializers.FloatField()


class StudentSnapshotSerializer(serializers.Serializer):
    student = _StudentWithCohortSerializer()
    skill_radar = SkillRadarItemSerializer(many=True)
    recurring_patterns = RecurringPatternSerializer(many=True)
    trending_up = serializers.ListField(child=serializers.CharField())
    trending_down = serializers.ListField(child=serializers.CharField())
    recent_activity = RecentActivitySerializer()
    suggested_interventions = serializers.ListField(child=serializers.DictField())


class TrajectoryWeekSerializer(serializers.Serializer):
    week_start = serializers.CharField()
    avg_score_per_category = serializers.DictField(child=serializers.FloatField())
    prs_count = serializers.IntegerField()
    findings_count = serializers.IntegerField()


class TrajectoryMilestoneSerializer(serializers.Serializer):
    date = serializers.CharField(allow_null=True)
    event = serializers.CharField()
    skill = serializers.CharField(allow_blank=True)


class StudentTrajectorySerializer(serializers.Serializer):
    student = _StudentRefSerializer()
    weeks = TrajectoryWeekSerializer(many=True)
    milestones = TrajectoryMilestoneSerializer(many=True)


class PRHistoryEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    pr_url = serializers.CharField()
    pr_number = serializers.IntegerField()
    pr_title = serializers.CharField(allow_blank=True)
    repo_full_name = serializers.CharField()
    submitted_at = serializers.CharField(allow_null=True)
    graded_at = serializers.CharField(allow_null=True)
    state = serializers.CharField()
    rubric_score_avg = serializers.FloatField(allow_null=True)
    findings_count = serializers.IntegerField()
    course_name = serializers.CharField(allow_null=True)


class StudentPRHistorySerializer(serializers.Serializer):
    student = _StudentRefSerializer()
    sessions = PRHistoryEntrySerializer(many=True)
