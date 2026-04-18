"""
DRF serializers for the grading app.

Design choice: ViewSets + router instead of the APIView pattern used
elsewhere in this repo. Grading has many similar CRUD surfaces (Classroom,
Rubric, Submission, GradingSession) with custom actions (send, resume,
generate_draft). ViewSets are ~40% less boilerplate and idiomatic DRF.

Rubric criteria JSON is validated at save time so a malformed rubric never
reaches the rubric_grader service (RubricSchemaError would be runtime).
"""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    Classroom,
    ClassroomMembership,
    GradingSession,
    LLMCostLog,
    PostedComment,
    Rubric,
    SessionEvaluation,
    Submission,
)


# ─────────────────────────────────────────────────────────────────────────────
# Rubric
# ─────────────────────────────────────────────────────────────────────────────
class RubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rubric
        fields = [
            "id",
            "org",
            "owner",
            "is_template",
            "name",
            "criteria",
            "calibration",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "org", "owner", "is_template", "created_at", "updated_at"]

    def validate_criteria(self, value):
        """
        Validate rubric criteria shape BEFORE save.
        Shape: list of {id, name, weight, levels:[{score, description}, ...]}.
        """
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("criteria must be a non-empty list")
        seen_ids = set()
        for i, c in enumerate(value):
            if not isinstance(c, dict):
                raise serializers.ValidationError(f"criterion {i} must be an object")
            for key in ("id", "name", "levels"):
                if key not in c:
                    raise serializers.ValidationError(f"criterion {i} missing '{key}'")
            if c["id"] in seen_ids:
                raise serializers.ValidationError(f"duplicate criterion id: {c['id']}")
            seen_ids.add(c["id"])
            weight = c.get("weight", 1.0)
            try:
                float(weight)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    f"criterion {c['id']}: weight must be numeric"
                )
            levels = c["levels"]
            if not isinstance(levels, list) or len(levels) < 2:
                raise serializers.ValidationError(
                    f"criterion {c['id']}: levels must be a list of 2+ entries"
                )
            for j, lvl in enumerate(levels):
                if not isinstance(lvl, dict) or "score" not in lvl:
                    raise serializers.ValidationError(
                        f"criterion {c['id']} level {j}: must be object with 'score'"
                    )
        return value

    def validate_calibration(self, value):
        """Calibration is optional but must be a dict if present."""
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("calibration must be an object")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Classroom + Membership
# ─────────────────────────────────────────────────────────────────────────────
class ClassroomMembershipSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.email", read_only=True)
    student_name = serializers.CharField(source="student.display_name", read_only=True)

    class Meta:
        model = ClassroomMembership
        fields = [
            "id",
            "classroom",
            "student",
            "student_email",
            "student_name",
            "student_repo_url",
            "joined_at",
        ]
        read_only_fields = ["id", "joined_at"]


class ClassroomSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    rubric_name = serializers.CharField(source="rubric.name", read_only=True, default=None)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = [
            "id",
            "org",
            "owner",
            "owner_email",
            "secondary_docent",
            "name",
            "source_control_type",
            "target_branch_pattern",
            "rubric",
            "rubric_name",
            "starts_at",
            "ends_at",
            "student_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "org",
            "owner",
            "owner_email",
            "rubric_name",
            "student_count",
            "created_at",
            "updated_at",
        ]

    def get_student_count(self, obj) -> int:
        return obj.memberships.count()


# ─────────────────────────────────────────────────────────────────────────────
# Submission
# ─────────────────────────────────────────────────────────────────────────────
class SubmissionSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.email", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    has_grading_session = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "org",
            "classroom",
            "classroom_name",
            "student",
            "student_email",
            "repo_full_name",
            "pr_number",
            "pr_url",
            "pr_title",
            "base_branch",
            "head_branch",
            "status",
            "due_at",
            "has_grading_session",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "org",
            "classroom_name",
            "student_email",
            "has_grading_session",
            "created_at",
            "updated_at",
        ]

    def get_has_grading_session(self, obj) -> bool:
        return hasattr(obj, "grading_session")


# ─────────────────────────────────────────────────────────────────────────────
# GradingSession
# ─────────────────────────────────────────────────────────────────────────────
class PostedCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostedComment
        fields = [
            "id",
            "client_mutation_id",
            "github_comment_id",
            "file_path",
            "line_number",
            "body_preview",
            "posted_at",
        ]
        read_only_fields = fields


class GradingSessionListSerializer(serializers.ModelSerializer):
    """Lean serializer for inbox list views. No draft payload."""

    student_email = serializers.EmailField(source="submission.student.email", read_only=True)
    student_name = serializers.CharField(
        source="submission.student.display_name", read_only=True
    )
    classroom_id = serializers.IntegerField(source="submission.classroom_id", read_only=True)
    classroom_name = serializers.CharField(
        source="submission.classroom.name", read_only=True
    )
    pr_url = serializers.URLField(source="submission.pr_url", read_only=True)
    pr_title = serializers.CharField(source="submission.pr_title", read_only=True)
    due_at = serializers.DateTimeField(source="submission.due_at", read_only=True)

    class Meta:
        model = GradingSession
        fields = [
            "id",
            "state",
            "submission",
            "student_email",
            "student_name",
            "classroom_id",
            "classroom_name",
            "pr_url",
            "pr_title",
            "due_at",
            "ai_draft_generated_at",
            "posted_at",
            "docent_review_time_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GradingSessionDetailSerializer(serializers.ModelSerializer):
    """Full serializer for the grading detail view. Includes draft payload."""

    student_email = serializers.EmailField(source="submission.student.email", read_only=True)
    student_name = serializers.CharField(
        source="submission.student.display_name", read_only=True
    )
    classroom_name = serializers.CharField(
        source="submission.classroom.name", read_only=True
    )
    pr_url = serializers.URLField(source="submission.pr_url", read_only=True)
    pr_title = serializers.CharField(source="submission.pr_title", read_only=True)
    rubric_snapshot = serializers.SerializerMethodField()
    posted_comments = PostedCommentSerializer(many=True, read_only=True)

    class Meta:
        model = GradingSession
        fields = [
            "id",
            "state",
            "submission",
            "student_email",
            "student_name",
            "classroom_name",
            "pr_url",
            "pr_title",
            "rubric",
            "rubric_snapshot",
            "ai_draft_scores",
            "ai_draft_comments",
            "ai_draft_model",
            "ai_draft_generated_at",
            "ai_draft_truncated",
            "final_scores",
            "final_comments",
            "final_summary",
            "docent_review_started_at",
            "docent_review_time_seconds",
            "sending_started_at",
            "posted_at",
            "partial_post_error",
            "posted_comments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state",
            "submission",
            "student_email",
            "student_name",
            "classroom_name",
            "pr_url",
            "pr_title",
            "rubric",
            "rubric_snapshot",
            "ai_draft_scores",
            "ai_draft_comments",
            "ai_draft_model",
            "ai_draft_generated_at",
            "ai_draft_truncated",
            "sending_started_at",
            "posted_at",
            "partial_post_error",
            "posted_comments",
            "created_at",
            "updated_at",
        ]

    def get_rubric_snapshot(self, obj) -> dict:
        """Denormalized rubric data so the frontend doesn't need a second round-trip."""
        r = obj.rubric
        return {
            "id": r.id,
            "name": r.name,
            "criteria": r.criteria,
            "calibration": r.calibration,
        }


class GradingSessionEditSerializer(serializers.ModelSerializer):
    """Used on PATCH: only the docent-editable fields are writable."""

    class Meta:
        model = GradingSession
        fields = [
            "final_scores",
            "final_comments",
            "final_summary",
            "docent_review_started_at",
            "docent_review_time_seconds",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# LLM cost (admin-internal)
# ─────────────────────────────────────────────────────────────────────────────
class LLMCostLogSerializer(serializers.ModelSerializer):
    docent_email = serializers.EmailField(source="docent.email", read_only=True, default=None)
    classroom_name = serializers.CharField(
        source="classroom.name", read_only=True, default=None
    )

    class Meta:
        model = LLMCostLog
        fields = [
            "id",
            "tier",
            "model_name",
            "docent",
            "docent_email",
            "classroom",
            "classroom_name",
            "tokens_in",
            "tokens_out",
            "cost_eur",
            "latency_ms",
            "ceiling_rejected",
            "occurred_at",
        ]
        read_only_fields = fields
