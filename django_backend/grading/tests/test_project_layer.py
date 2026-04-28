"""
Tests for the Project + StudentProjectRepo layer (Apr 28 2026).

Hierarchy: Cohort → Course → Project → StudentProjectRepo → Submission

Permission contract under test:

  Cohort      — school admin creates (verified elsewhere).
  Course      — school admin creates (newly tightened in this branch).
  Project     — TEACHER creates (the course owner). NOT school admin.
                Admins can override as escape hatch.
  StudentProjectRepo — STUDENT creates own row. Cannot create for peers.
                       Teacher who owns the project's course gets read-only.

Webhook routing:
  When a student has registered a StudentProjectRepo for a project, an
  incoming PR matching that repo URL routes to that project's course
  (overriding the legacy first-course-in-cohort heuristic) and stamps
  Submission.project with the matched project FK.

Cost metering:
  log_llm_call() now accepts a `prompt_version` kwarg — defaults to ""
  for legacy callers, populated incrementally by services that opt in.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    LLMCostLog,
    Project,
    Rubric,
    StudentProjectRepo,
    Submission,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def org(db):
    from users.models import Organization
    return Organization.objects.create(name="Test School", slug="test-school")


@pytest.fixture
def admin(db, org):
    return User.objects.create_user(
        username="admin", email="admin@example.com", password="pw",
        role="admin", organization=org,
    )


@pytest.fixture
def teacher(db, org):
    return User.objects.create_user(
        username="teacher", email="teacher@example.com", password="pw",
        role="teacher", organization=org,
    )


@pytest.fixture
def teacher_other(db, org):
    """Another teacher in the same org who does NOT own the course."""
    return User.objects.create_user(
        username="teacher_other", email="other@example.com", password="pw",
        role="teacher", organization=org,
    )


@pytest.fixture
def student(db, org):
    return User.objects.create_user(
        username="student", email="student@example.com", password="pw",
        role="developer", organization=org,
    )


@pytest.fixture
def student_other(db, org):
    """Another student in the same cohort — used for peer-permission checks."""
    return User.objects.create_user(
        username="student_other", email="student_other@example.com", password="pw",
        role="developer", organization=org,
    )


@pytest.fixture
def rubric(db, org):
    return Rubric.objects.create(
        org=org, name="Default Rubric",
        criteria=[{"id": "x", "name": "X", "weight": 1.0,
                   "levels": [{"score": 1, "description": "fail"},
                              {"score": 4, "description": "excellent"}]}],
    )


@pytest.fixture
def cohort(db, org):
    return Cohort.objects.create(org=org, name="Klas 2A")


@pytest.fixture
def course(db, org, cohort, teacher, rubric):
    return Course.objects.create(
        org=org, cohort=cohort, owner=teacher, rubric=rubric, name="Backend",
    )


@pytest.fixture
def membership(db, cohort, student):
    return CohortMembership.objects.create(
        cohort=cohort, student=student, student_repo_url="",
    )


@pytest.fixture
def project(db, course, teacher):
    return Project.objects.create(
        course=course, name="Build a REST API",
        description="Phase 1 assignment",
        created_by=teacher,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Project creation permissions
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestProjectCreatePermissions:
    """Project creation: only the course owner (or admin)."""

    def test_course_owner_can_create_project(self, course, teacher):
        """The teacher who owns the course can create a project under it."""
        client = APIClient()
        client.force_authenticate(user=teacher)
        resp = client.post(
            "/api/grading/projects/",
            data={"course": course.id, "name": "Auth", "description": "Ph2"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert Project.objects.filter(course=course, name="Auth").exists()

    def test_other_teacher_cannot_create_under_someone_elses_course(
        self, course, teacher_other,
    ):
        """A teacher who doesn't own the course gets 403 — not their assignment to define."""
        client = APIClient()
        client.force_authenticate(user=teacher_other)
        resp = client.post(
            "/api/grading/projects/",
            data={"course": course.id, "name": "Sneaky", "description": ""},
            format="json",
        )
        assert resp.status_code == 403, resp.content

    def test_student_cannot_create_project(self, course, student):
        """Students never create projects."""
        client = APIClient()
        client.force_authenticate(user=student)
        resp = client.post(
            "/api/grading/projects/",
            data={"course": course.id, "name": "Student-attempt", "description": ""},
            format="json",
        )
        assert resp.status_code == 403, resp.content

    def test_admin_can_create_project_on_any_course(self, course, admin):
        """Admin override is allowed for support cases."""
        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.post(
            "/api/grading/projects/",
            data={"course": course.id, "name": "Admin-created", "description": ""},
            format="json",
        )
        assert resp.status_code == 201, resp.content


# ─────────────────────────────────────────────────────────────────────────────
# StudentProjectRepo self-service
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestStudentProjectRepoSelfService:
    """Students set their own repo URLs. They cannot set them for peers."""

    def test_student_creates_own_repo(self, project, student, membership):
        client = APIClient()
        client.force_authenticate(user=student)
        resp = client.post(
            "/api/grading/student-project-repos/",
            data={
                "project": project.id,
                "repo_url": "https://github.com/student/rest-api",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        repo = StudentProjectRepo.objects.get(project=project, student=student)
        assert repo.repo_url == "https://github.com/student/rest-api"
        assert repo.org_id == project.org_id

    def test_student_cannot_create_repo_for_peer(
        self, project, student, student_other, membership,
    ):
        """Student tries to pass a different `student` field — server forces self."""
        client = APIClient()
        client.force_authenticate(user=student)
        resp = client.post(
            "/api/grading/student-project-repos/",
            data={
                "project": project.id,
                "student": student_other.id,  # attempting to write peer's row
                "repo_url": "https://github.com/student/forged",
            },
            format="json",
        )
        # Either server forces self (preferred — happens silently) OR rejects.
        # Our impl forces self via perform_create, so the row gets created
        # for the requesting user, NOT the passed-in student.
        assert resp.status_code == 201, resp.content
        # Verify NO row was created for the peer.
        assert not StudentProjectRepo.objects.filter(
            project=project, student=student_other,
        ).exists()
        # And one was created for the requesting user.
        assert StudentProjectRepo.objects.filter(
            project=project, student=student,
        ).exists()

    def test_student_can_update_own_repo(self, project, student, membership):
        repo = StudentProjectRepo.objects.create(
            project=project, student=student, org=project.org,
            repo_url="https://github.com/student/old",
        )
        client = APIClient()
        client.force_authenticate(user=student)
        resp = client.patch(
            f"/api/grading/student-project-repos/{repo.id}/",
            data={"repo_url": "https://github.com/student/new"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        repo.refresh_from_db()
        assert repo.repo_url == "https://github.com/student/new"

    def test_student_cannot_update_peers_repo(
        self, project, student, student_other,
    ):
        peer_repo = StudentProjectRepo.objects.create(
            project=project, student=student_other, org=project.org,
            repo_url="https://github.com/peer/repo",
        )
        client = APIClient()
        client.force_authenticate(user=student)
        resp = client.patch(
            f"/api/grading/student-project-repos/{peer_repo.id}/",
            data={"repo_url": "https://github.com/student/hijacked"},
            format="json",
        )
        # 404 (org-scoped manager hides it from the queryset) or 403 are both
        # acceptable — both prevent the write. We verify the row is unchanged.
        assert resp.status_code in {403, 404}, resp.content
        peer_repo.refresh_from_db()
        assert peer_repo.repo_url == "https://github.com/peer/repo"

    def test_teacher_can_list_repos_for_their_courses_projects(
        self, project, student, teacher, membership,
    ):
        StudentProjectRepo.objects.create(
            project=project, student=student, org=project.org,
            repo_url="https://github.com/student/api",
        )
        client = APIClient()
        client.force_authenticate(user=teacher)
        resp = client.get(f"/api/grading/student-project-repos/?project={project.id}")
        assert resp.status_code == 200, resp.content
        # Teacher sees the student's row (read-only access).
        urls = [r["repo_url"] for r in resp.json().get("results", resp.json())]
        assert "https://github.com/student/api" in urls


# ─────────────────────────────────────────────────────────────────────────────
# Course-create permission tightening
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCourseCreateTightenedToAdmin:
    """As of Apr 28 2026, only school admins can POST /courses/."""

    def test_admin_can_create_course(self, cohort, admin, teacher, rubric):
        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.post(
            "/api/grading/courses/",
            data={"cohort": cohort.id, "owner": teacher.id, "name": "Frontend"},
            format="json",
        )
        assert resp.status_code == 201, resp.content

    def test_teacher_cannot_create_course(self, cohort, teacher, rubric):
        """Backend leak fix: teacher tried to bypass the frontend-only gate."""
        client = APIClient()
        client.force_authenticate(user=teacher)
        resp = client.post(
            "/api/grading/courses/",
            data={"cohort": cohort.id, "owner": teacher.id, "name": "Sneaky"},
            format="json",
        )
        assert resp.status_code == 403, resp.content


# ─────────────────────────────────────────────────────────────────────────────
# OrgScopedManager isolation for the new models
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestProjectOrgIsolation:
    """A user from org B cannot see org A's projects or repos."""

    def test_cross_org_project_invisible(self, project, db):
        """User in a different org gets an empty list, not 403, to avoid enumeration."""
        from users.models import Organization
        other_org = Organization.objects.create(name="Other Org", slug="other-org")
        intruder = User.objects.create_user(
            username="intruder", email="intruder@example.com", password="pw",
            role="admin", organization=other_org,
        )
        client = APIClient()
        client.force_authenticate(user=intruder)
        resp = client.get("/api/grading/projects/")
        assert resp.status_code == 200, resp.content
        results = resp.json().get("results", resp.json())
        ids = [p["id"] for p in results]
        assert project.id not in ids


# ─────────────────────────────────────────────────────────────────────────────
# LLMCostLog.prompt_version
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPromptVersionField:
    """Cost log accepts and persists the new prompt_version field."""

    def test_log_llm_call_accepts_prompt_version(self, org, course):
        from grading.services.cost_metering import log_llm_call
        log = log_llm_call(
            org_id=org.id,
            tier="cheap",
            model_name="claude-haiku",
            tokens_in=100,
            tokens_out=50,
            course_id=course.id,
            prompt_version="rubric_grader_v3",
        )
        assert log.prompt_version == "rubric_grader_v3"

    def test_log_llm_call_default_empty_prompt_version(self, org):
        """Existing callers that don't pass prompt_version remain unaffected."""
        from grading.services.cost_metering import log_llm_call
        log = log_llm_call(
            org_id=org.id,
            tier="cheap",
            model_name="claude-haiku",
            tokens_in=100,
            tokens_out=50,
        )
        assert log.prompt_version == ""


# ─────────────────────────────────────────────────────────────────────────────
# Webhook routing — StudentProjectRepo wins over legacy CohortMembership
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestWebhookProjectRouting:
    """When a StudentProjectRepo matches, the Submission gets project + correct course."""

    def test_match_project_for_submission_returns_project(
        self, project, student, membership,
    ):
        from grading.webhooks import _match_project_for_submission
        StudentProjectRepo.objects.create(
            project=project, student=student, org=project.org,
            repo_url="https://github.com/student/rest-api",
        )
        matched = _match_project_for_submission(
            repo_full_name="student/rest-api",
            student_id=student.id,
        )
        assert matched is not None
        assert matched.id == project.id

    def test_match_project_returns_none_when_no_repo(
        self, project, student, membership,
    ):
        """Student never registered a repo — the matcher returns None."""
        from grading.webhooks import _match_project_for_submission
        matched = _match_project_for_submission(
            repo_full_name="student/rest-api",
            student_id=student.id,
        )
        assert matched is None

    def test_match_project_skips_archived(
        self, project, student, membership,
    ):
        """Archived projects don't catch new submissions."""
        from django.utils import timezone
        from grading.webhooks import _match_project_for_submission

        StudentProjectRepo.objects.create(
            project=project, student=student, org=project.org,
            repo_url="https://github.com/student/rest-api",
        )
        project.archived_at = timezone.now()
        project.save()

        matched = _match_project_for_submission(
            repo_full_name="student/rest-api",
            student_id=student.id,
        )
        assert matched is None
