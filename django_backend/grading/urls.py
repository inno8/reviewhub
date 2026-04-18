"""
URL routing for the grading app.

DRF router mounts CRUD + custom actions at /api/grading/<resource>/.
Plus a separate (CSRF-exempt, auth-less) GitHub webhook endpoint for
real PR events. See views.py + webhooks.py for docs.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views, webhooks

router = DefaultRouter()
router.register(r"rubrics", views.RubricViewSet, basename="rubric")
router.register(r"classrooms", views.ClassroomViewSet, basename="classroom")
router.register(r"submissions", views.SubmissionViewSet, basename="submission")
router.register(r"sessions", views.GradingSessionViewSet, basename="grading-session")
router.register(r"cost-logs", views.LLMCostLogViewSet, basename="llm-cost-log")

urlpatterns = router.urls + [
    path("webhooks/github/", webhooks.github_webhook, name="grading-github-webhook"),
]
