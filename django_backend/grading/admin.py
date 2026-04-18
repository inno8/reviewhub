"""
Django admin registration for the grading app.

For v1 internal dogfood, the teacher creates rubrics, classrooms, and initial
test submissions via Django admin. Teacher-facing UI for rubric CRUD lands
in v1.1 before Media College external outreach.

Admin URL: http://localhost:8000/admin/grading/
"""
from django.contrib import admin

from .models import (
    Classroom,
    ClassroomMembership,
    GradingSession,
    LLMCostLog,
    PostedComment,
    Rubric,
    SessionEvaluation,
    Submission,
    WebhookDelivery,
)


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("name", "org", "owner", "is_template", "updated_at")
    list_filter = ("is_template", "org")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "org", "owner", "rubric", "source_control_type", "created_at")
    list_filter = ("source_control_type", "org")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClassroomMembership)
class ClassroomMembershipAdmin(admin.ModelAdmin):
    list_display = ("classroom", "student", "student_repo_url", "joined_at")
    search_fields = ("student__email", "classroom__name", "student_repo_url")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "student", "classroom", "repo_full_name", "pr_number",
        "status", "due_at", "created_at",
    )
    list_filter = ("status", "classroom")
    search_fields = ("repo_full_name", "pr_title", "student__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(GradingSession)
class GradingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "submission", "state", "ai_draft_model",
        "docent_review_time_seconds", "posted_at", "updated_at",
    )
    list_filter = ("state",)
    search_fields = ("submission__repo_full_name",)
    readonly_fields = (
        "ai_draft_scores", "ai_draft_comments", "ai_draft_model",
        "ai_draft_generated_at", "ai_draft_truncated",
        "docent_review_started_at", "docent_review_time_seconds",
        "sending_started_at", "posted_at", "partial_post_error",
        "created_at", "updated_at",
    )


@admin.register(SessionEvaluation)
class SessionEvaluationAdmin(admin.ModelAdmin):
    list_display = ("grading_session", "evaluation", "included_in_draft")


@admin.register(PostedComment)
class PostedCommentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "grading_session", "file_path", "line_number",
        "github_comment_id", "posted_at",
    )
    search_fields = ("file_path", "body_preview")
    readonly_fields = (
        "grading_session", "client_mutation_id", "github_comment_id",
        "file_path", "line_number", "body_preview", "posted_at",
    )


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("provider", "delivery_id", "event_type", "received_at")
    list_filter = ("provider", "event_type")
    search_fields = ("delivery_id",)
    readonly_fields = ("provider", "delivery_id", "event_type", "received_at")


@admin.register(LLMCostLog)
class LLMCostLogAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at", "tier", "model_name", "docent", "classroom",
        "tokens_in", "tokens_out", "cost_eur", "ceiling_rejected",
    )
    list_filter = ("tier", "model_name", "ceiling_rejected")
    search_fields = ("model_name", "docent__email")
    readonly_fields = tuple(f.name for f in LLMCostLog._meta.fields)
