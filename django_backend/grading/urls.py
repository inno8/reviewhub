"""
URL routing for the grading app.

DRF router mounts CRUD + custom actions at /api/grading/<resource>/.
Plus a separate (CSRF-exempt, auth-less) GitHub webhook endpoint for
real PR events. See views.py + webhooks.py for docs.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import (
    ops_views,
    views,
    views_cohort_intelligence,
    views_file_fetch,
    views_student_intelligence,
    webhooks,
)

router = DefaultRouter()
router.register(r"rubrics", views.RubricViewSet, basename="rubric")
router.register(r"cohorts", views.CohortViewSet, basename="cohort")
router.register(r"courses", views.CourseViewSet, basename="course")
router.register(r"submissions", views.SubmissionViewSet, basename="submission")
router.register(r"sessions", views.GradingSessionViewSet, basename="grading-session")
router.register(r"projects", views.ProjectViewSet, basename="project")
router.register(
    r"student-project-repos",
    views.StudentProjectRepoViewSet,
    basename="student-project-repo",
)
router.register(r"cost-logs", views.LLMCostLogViewSet, basename="llm-cost-log")

urlpatterns = router.urls + [
    # GitHub PR webhooks — public, signature-verified
    path("webhooks/github/", webhooks.github_webhook, name="grading-github-webhook"),
    # Ops dashboard — superuser-only, v1 read-only
    path("ops/summary/", ops_views.OpsSummaryView.as_view(), name="ops-summary"),
    path("ops/orgs/", ops_views.OpsOrgsView.as_view(), name="ops-orgs"),
    path("ops/courses/", ops_views.OpsCoursesView.as_view(), name="ops-courses"),
    path("ops/teachers/", ops_views.OpsTeacherCostsView.as_view(), name="ops-teachers"),
    path("ops/llm-log/", ops_views.OpsLLMCallLogView.as_view(), name="ops-llm-log"),
    # Workstream I1 — passive weekly metrics (admin + superuser)
    path(
        "ops/metrics/weekly/",
        ops_views.OpsWeeklyMetricsView.as_view(),
        name="ops-weekly-metrics",
    ),
    # Teacher's roster — all students across their cohorts
    path(
        "students/",
        views_student_intelligence.TeacherStudentListView.as_view(),
        name="teacher-student-list",
    ),
    # Workstream D — student-intelligence (teacher-facing)
    path(
        "students/<int:student_id>/snapshot/",
        views_student_intelligence.StudentSnapshotView.as_view(),
        name="student-snapshot",
    ),
    path(
        "students/<int:student_id>/trajectory/",
        views_student_intelligence.StudentTrajectoryView.as_view(),
        name="student-trajectory",
    ),
    path(
        "students/<int:student_id>/pr-history/",
        views_student_intelligence.StudentPRHistoryView.as_view(),
        name="student-pr-history",
    ),
    path(
        "cohorts/<int:cohort_id>/recurring-errors/",
        views_student_intelligence.CohortRecurringErrorsView.as_view(),
        name="cohort-recurring-errors",
    ),
    path(
        "cohorts/<int:cohort_id>/overview/",
        views_cohort_intelligence.CohortOverviewView.as_view(),
        name="cohort-overview",
    ),
    # View-in-code modal: fetch file content from GitHub for a session
    path(
        "sessions/<int:pk>/file/",
        views_file_fetch.GradingSessionFileContentView.as_view(),
        name="grading-session-file",
    ),
]
