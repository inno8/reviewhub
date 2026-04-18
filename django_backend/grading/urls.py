"""
URL routing for the grading app.

DRF router mounts CRUD + custom actions at /api/grading/<resource>/.
See views.py for action documentation.
"""
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"rubrics", views.RubricViewSet, basename="rubric")
router.register(r"classrooms", views.ClassroomViewSet, basename="classroom")
router.register(r"submissions", views.SubmissionViewSet, basename="submission")
router.register(r"sessions", views.GradingSessionViewSet, basename="grading-session")
router.register(r"cost-logs", views.LLMCostLogViewSet, basename="llm-cost-log")

urlpatterns = router.urls
