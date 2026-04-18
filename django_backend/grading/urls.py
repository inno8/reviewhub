"""
URL routing for the grading app.

DRF router mounts CRUD + custom actions at /api/grading/<resource>/.
Plus a separate (CSRF-exempt, auth-less) GitHub webhook endpoint for
real PR events. See views.py + webhooks.py for docs.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import ops_views, views, webhooks

router = DefaultRouter()
router.register(r"rubrics", views.RubricViewSet, basename="rubric")
router.register(r"classrooms", views.ClassroomViewSet, basename="classroom")
router.register(r"submissions", views.SubmissionViewSet, basename="submission")
router.register(r"sessions", views.GradingSessionViewSet, basename="grading-session")
router.register(r"cost-logs", views.LLMCostLogViewSet, basename="llm-cost-log")

urlpatterns = router.urls + [
    # GitHub PR webhooks — public, signature-verified
    path("webhooks/github/", webhooks.github_webhook, name="grading-github-webhook"),
    # Ops dashboard — superuser-only, v1 read-only
    path("ops/summary/", ops_views.OpsSummaryView.as_view(), name="ops-summary"),
    path("ops/orgs/", ops_views.OpsOrgsView.as_view(), name="ops-orgs"),
    path("ops/classrooms/", ops_views.OpsClassroomsView.as_view(), name="ops-classrooms"),
    path("ops/teachers/", ops_views.OpsTeacherCostsView.as_view(), name="ops-teachers"),
    path("ops/llm-log/", ops_views.OpsLLMCallLogView.as_view(), name="ops-llm-log"),
]
