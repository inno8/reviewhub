"""
DRF ViewSets for the grading app.

Security boundary:
  - Every ViewSet's .get_queryset() starts from Model.objects.for_user(user).
    That method filters by org via OrgScopedManager. It is the ONE place a
    cross-org leak could happen, and it is covered by test_org_isolation.
  - TEACHER role is required for CRUD actions. Students get read-only access
    to their own rows only (handled by IsTeacherOrReadOnlyStudent).

Custom actions on GradingSessionViewSet:
  - POST .../generate_draft/  — kick off the rubric grader (state: pending/drafted → drafting → drafted).
  - POST .../send/            — post approved comments to GitHub (state: drafted/reviewing → sending → posted/partial).
  - POST .../resume/          — resume a partial send (state: partial → sending → posted).
  - POST .../start_review/    — docent opens the session (state: drafted → reviewing; starts the stopwatch).

Concurrency (eng-review bundle):
  - generate_draft + send + resume all use select_for_update via
    GradingSession.objects.select_for_update().
  - state transitions go through GradingSession.can_transition_to() for
    defense in depth.
  - The actual GitHub posting (and its partial-post recovery) lives in
    grading.services.github_poster (Day 7-8, not yet implemented).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from django.http import Http404
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Cohort,
    CohortMembership,
    CohortTeacher,
    Course,
    GradingSession,
    LLMCostLog,
    Rubric,
    Submission,
)
from .permissions import (
    IsCohortVisible,
    IsCourseOwnerOrAdmin,
    IsOrgAdmin,
    IsTeacher,
    IsTeacherOrAdmin,
    IsTeacherOrReadOnlyStudent,
)
from .serializers import (
    CohortMembershipSerializer,
    CohortSerializer,
    CohortTeacherSerializer,
    CourseSerializer,
    GradingSessionDetailSerializer,
    GradingSessionEditSerializer,
    GradingSessionListSerializer,
    LLMCostLogSerializer,
    RubricSerializer,
    SubmissionSerializer,
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Rubric
# ─────────────────────────────────────────────────────────────────────────────
class RubricViewSet(viewsets.ModelViewSet):
    """
    /api/grading/rubrics/
    List/CRUD rubrics the requesting user can see:
      - Templates (is_template=True): visible to everyone in the org.
      - Org rubrics: visible to all teachers in the same org.

    Students don't create or edit rubrics.
    """

    serializer_class = RubricSerializer
    permission_classes = [IsAuthenticated, IsTeacher]

    def get_queryset(self):
        user = self.request.user
        # for_user() filters by org; we also include global templates (org=null).
        base = Rubric.objects.for_user(user)
        # Union with templates:
        templates = Rubric.objects.filter(is_template=True)
        return (base | templates).distinct().order_by("-updated_at")

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(org=user.organization, owner=user, is_template=False)


# ─────────────────────────────────────────────────────────────────────────────
# Cohort (admin-managed, teachers + students read-scoped)
# ─────────────────────────────────────────────────────────────────────────────
def _role(user) -> str:
    return getattr(user, "role", "") or ""


def _is_admin(user) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    return _role(user) == "admin"


def _is_teacher(user) -> bool:
    return _role(user) == "teacher"


class CohortViewSet(viewsets.ModelViewSet):
    """
    /api/grading/cohorts/

    Admin write, teacher/student scoped read.

    Visibility:
      - admin / superuser: all cohorts in their org
      - teacher: cohorts where they own (or secondary-teach) a course
      - student: their own cohort (via CohortMembership)

    Writes (POST, PATCH, archive, DELETE of membership rows) are admin-only.
    Hard DELETE of a cohort is not exposed — use archive/ instead so grading
    history stays queryable.
    """

    serializer_class = CohortSerializer

    def get_permissions(self):
        # Writes require admin; reads require any authenticated role that
        # has a relationship to the cohort (enforced via queryset scoping).
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        if self.action in {"members", "teachers"}:
            # GET/POST/DELETE on members/teachers is permission-checked inside
            # the action (GET open to all, POST/DELETE admin-only).
            return [IsAuthenticated()]
        # create, update, partial_update, destroy, archive
        return [IsAuthenticated(), IsOrgAdmin()]

    def get_queryset(self):
        user = self.request.user
        base = Cohort.objects.for_user(user).select_related("org")
        include_archived = self.request.query_params.get("include_archived") == "true"
        if not include_archived and self.action == "list":
            base = base.filter(archived_at__isnull=True)

        if _is_admin(user):
            return base.order_by("-created_at")
        if _is_teacher(user):
            # Cohorts where the teacher is explicitly assigned, owns a course,
            # or is secondary docent.
            return (
                base.filter(teacher_assignments__teacher=user)
                | base.filter(courses__owner=user)
                | base.filter(courses__secondary_docent=user)
            ).distinct().order_by("-created_at")
        # Student: their own cohort only
        return base.filter(memberships__student=user, memberships__removed_at__isnull=True).distinct()

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(org=user.organization)

    def destroy(self, request, *args, **kwargs):
        # Hard delete is disallowed — archive via dedicated action instead.
        return Response(
            {"error": "hard_delete_disabled", "message": "Use POST /archive/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        """
        Soft-archive a cohort. Admins only. Idempotent: re-archiving is a no-op.
        """
        cohort = self.get_object()  # 404 if not visible to this user
        # Re-check admin (get_permissions already enforces; belt-and-braces)
        if not _is_admin(request.user):
            raise PermissionDenied("Admin role required.")
        if cohort.archived_at is None:
            cohort.archived_at = timezone.now()
            cohort.save(update_fields=["archived_at", "updated_at"])
        return Response(CohortSerializer(cohort).data)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        """
        GET   /cohorts/{id}/members/        list active members (admin, any
                                            teacher in the cohort, or the
                                            students themselves)
        POST  /cohorts/{id}/members/        add student (admin only)
                                            body: {student_id, student_repo_url?}
        """
        cohort = self.get_object()  # 404 if not visible to this user

        if request.method == "GET":
            qs = cohort.memberships.filter(removed_at__isnull=True).select_related("student").order_by("joined_at")
            return Response(CohortMembershipSerializer(qs, many=True).data)

        # POST — admin only
        if not _is_admin(request.user):
            raise PermissionDenied("Admin role required to add members.")

        student_id = request.data.get("student_id")
        repo_url = request.data.get("student_repo_url", "") or ""
        if not student_id:
            raise ValidationError({"student_id": "required"})

        from users.models import User
        try:
            student = User.objects.get(pk=student_id)
        except User.DoesNotExist:
            raise NotFound("student not found")
        if (
            not request.user.is_superuser
            and student.organization_id != request.user.organization_id
        ):
            raise PermissionDenied("student is in a different organization")

        existing = CohortMembership.objects.filter(
            student=student, removed_at__isnull=True
        ).select_related("cohort").first()
        if existing and existing.cohort_id != cohort.id:
            raise ValidationError(
                {
                    "student": (
                        f"student already enrolled in cohort "
                        f"{existing.cohort.name!r} (id={existing.cohort_id}) — "
                        "remove from that cohort first or transfer explicitly."
                    )
                }
            )

        m, created = CohortMembership.objects.update_or_create(
            student=student,
            defaults={
                "cohort": cohort,
                "student_repo_url": repo_url,
                "removed_at": None,
            },
        )
        return Response(
            CohortMembershipSerializer(m).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"members/(?P<membership_id>[^/.]+)",
    )
    def remove_member(self, request, pk=None, membership_id=None):
        """DELETE /cohorts/{id}/members/{membership_id}/  — admin only, soft-delete."""
        cohort = self.get_object()
        if not _is_admin(request.user):
            raise PermissionDenied("Admin role required to remove members.")
        try:
            m = cohort.memberships.get(pk=membership_id)
        except CohortMembership.DoesNotExist:
            raise NotFound("membership not found")
        if m.removed_at is None:
            m.removed_at = timezone.now()
            m.save(update_fields=["removed_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="teachers")
    def teachers(self, request, pk=None):
        """
        GET   /cohorts/{id}/teachers/   — list teachers assigned to this cohort.
        POST  /cohorts/{id}/teachers/   — add a teacher (admin only).
                                          body: {teacher_id}
        """
        cohort = self.get_object()

        if request.method == "GET":
            qs = cohort.teacher_assignments.select_related("teacher").order_by("added_at")
            return Response(CohortTeacherSerializer(qs, many=True).data)

        # POST — admin only
        if not _is_admin(request.user):
            raise PermissionDenied("Admin role required to add teachers.")

        teacher_id = request.data.get("teacher_id")
        if not teacher_id:
            raise ValidationError({"teacher_id": "required"})

        from users.models import User as _User
        try:
            teacher = _User.objects.get(pk=teacher_id)
        except _User.DoesNotExist:
            raise NotFound("teacher not found")

        if (
            not request.user.is_superuser
            and teacher.organization_id != request.user.organization_id
        ):
            raise PermissionDenied("teacher is in a different organization")

        if teacher.role not in ("teacher", "admin") and not teacher.is_superuser:
            raise ValidationError({"teacher_id": "user does not have a teacher role"})

        ct, created = CohortTeacher.objects.get_or_create(cohort=cohort, teacher=teacher)
        return Response(
            CohortTeacherSerializer(ct).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"teachers/(?P<assignment_id>[^/.]+)",
    )
    def remove_teacher(self, request, pk=None, assignment_id=None):
        """DELETE /cohorts/{id}/teachers/{assignment_id}/  — admin only."""
        cohort = self.get_object()
        if not _is_admin(request.user):
            raise PermissionDenied("Admin role required to remove teachers.")
        try:
            ct = cohort.teacher_assignments.get(pk=assignment_id)
        except CohortTeacher.DoesNotExist:
            raise NotFound("teacher assignment not found")
        ct.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────────────────────────────
# Course (was "Classroom")
# ─────────────────────────────────────────────────────────────────────────────
class CourseViewSet(viewsets.ModelViewSet):
    """
    /api/grading/courses/

    Visibility (org-scoped first via OrgScopedManager):
      - admin/superuser: every course in the org
      - teacher: courses they own, secondary-teach, OR any course in a
        cohort where they teach something (needed so co-teachers can see
        each other's courses in the same klas)
      - student: every course in their own cohort

    Writes:
      - create: admin (any cohort in org); teacher if they own the cohort
        (teach some course in it) OR they are setting themselves as owner
        in a cohort they teach
      - update: admin (any); teacher only when they own the course
      - reassign: admin-only — changes course.owner_id to new user in org
      - archive: via PATCH on archived_at or via POST /archive/ (admin + owner)

    Membership is also exposed here for v1 backward compatibility:
    /courses/{id}/members/ — delegates to the course's cohort.
    """

    serializer_class = CourseSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve", "members"}:
            return [IsAuthenticated()]
        if self.action in {"create"}:
            return [IsAuthenticated(), IsTeacherOrAdmin()]
        if self.action in {"reassign"}:
            return [IsAuthenticated(), IsOrgAdmin()]
        # update, partial_update, destroy, archive → owner-or-admin
        return [IsAuthenticated(), IsTeacherOrAdmin(), IsCourseOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        base = Course.objects.for_user(user).select_related("cohort", "owner", "rubric")
        include_archived = self.request.query_params.get("include_archived") == "true"
        if not include_archived and self.action == "list":
            base = base.filter(archived_at__isnull=True)

        if _is_admin(user):
            return base.order_by("-created_at")
        if _is_teacher(user):
            # Own + secondary + other courses in cohorts where I teach
            own = base.filter(owner=user)
            secondary = base.filter(secondary_docent=user)
            cohort_siblings = base.filter(
                cohort__courses__owner=user,
            ) | base.filter(cohort__courses__secondary_docent=user)
            return (own | secondary | cohort_siblings).distinct().order_by("-created_at")
        # Student: courses in their own cohort
        return base.filter(
            cohort__memberships__student=user,
            cohort__memberships__removed_at__isnull=True,
        ).distinct()

    def _resolve_create_payload(self, serializer):
        """
        Enforce create rules:
          - admin: may set any owner in the org; cohort must belong to org
          - teacher: may only create courses they will own themselves
            (owner defaults to self). Cohort must be in the teacher's org AND
            either empty of courses OR contain a course they already teach.
        """
        user = self.request.user
        data = serializer.validated_data
        cohort = data.get("cohort")
        if cohort is not None and cohort.org_id != user.organization_id and not user.is_superuser:
            raise PermissionDenied("cohort is in a different organization")

        if _is_admin(user):
            owner = data.get("owner") or user
            return {"org": user.organization, "owner": owner, "cohort": cohort}

        # Teacher path
        # Teachers cannot assign ownership to someone else.
        owner = data.get("owner")
        if owner is not None and owner.id != user.id:
            raise PermissionDenied("teachers can only create courses they own")
        if cohort is not None:
            already_teaching = (
                cohort.courses.filter(owner=user).exists()
                or cohort.courses.filter(secondary_docent=user).exists()
            )
            # If the cohort already has courses and the teacher teaches none
            # of them, creating there is an admin operation.
            if cohort.courses.exists() and not already_teaching:
                raise PermissionDenied("you don't teach in this cohort")
        return {"org": user.organization, "owner": user, "cohort": cohort}

    def perform_create(self, serializer):
        from django.db import IntegrityError
        overrides = self._resolve_create_payload(serializer)
        try:
            serializer.save(**overrides)
        except IntegrityError as exc:
            if "uniq_course_cohort_owner" in str(exc):
                raise ValidationError(
                    {"non_field_errors": [
                        "This teacher already owns an active course in this cohort. "
                        "A teacher can only have one course per cohort."
                    ]}
                )
            raise

    def perform_update(self, serializer):
        # Don't let non-admins mutate owner via plain PATCH.
        if not _is_admin(self.request.user):
            serializer.validated_data.pop("owner", None)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "hard_delete_disabled", "message": "Use POST /archive/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        """Soft-archive a course. Admin or the course owner."""
        course = self.get_object()
        self.check_object_permissions(request, course)
        if course.archived_at is None:
            course.archived_at = timezone.now()
            course.save(update_fields=["archived_at", "updated_at"])
        return Response(CourseSerializer(course).data)

    @action(detail=True, methods=["post"], url_path="reassign")
    def reassign(self, request, pk=None):
        """
        POST /courses/{id}/reassign/  body: {new_owner_id}
        Admin-only. Changes course.owner (e.g., teacher leaves school).
        """
        course = self.get_object()
        # IsOrgAdmin already enforced by get_permissions; keep defensive.
        if not _is_admin(request.user):
            raise PermissionDenied("Admin role required.")

        new_owner_id = request.data.get("new_owner_id")
        if not new_owner_id:
            raise ValidationError({"new_owner_id": "required"})
        from users.models import User
        try:
            new_owner = User.objects.get(pk=new_owner_id)
        except User.DoesNotExist:
            raise NotFound("new owner not found")
        if (
            not request.user.is_superuser
            and new_owner.organization_id != request.user.organization_id
        ):
            raise ValidationError({"new_owner_id": "user is in a different organization"})
        if _role(new_owner) not in {"teacher", "admin"}:
            raise ValidationError(
                {"new_owner_id": "new owner must have role=teacher or admin"}
            )
        course.owner = new_owner
        course.save(update_fields=["owner", "updated_at"])
        return Response(CourseSerializer(course).data)

    @action(detail=True, methods=["get", "post", "delete"], url_path="members")
    def members(self, request, pk=None):
        """
        GET    /courses/{id}/members/   → list (cohort memberships for this course's cohort)
        POST   /courses/{id}/members/   → {student_id, student_repo_url} add to cohort
        DELETE /courses/{id}/members/?student_id=X → remove from cohort

        In v1 Scope B1 Workstream A, membership is at the cohort level but this
        endpoint bridges the existing Classroom-era UI. A student added here
        joins the course's cohort (and thus every course in that cohort).
        """
        course = self.get_object()
        cohort = course.cohort

        if request.method == "GET":
            if cohort is None:
                return Response([])
            qs = cohort.memberships.select_related("student").order_by("joined_at")
            return Response(CohortMembershipSerializer(qs, many=True).data)

        if cohort is None:
            raise ValidationError({"cohort": "course has no cohort; assign one before managing members"})

        if request.method == "POST":
            student_id = request.data.get("student_id")
            repo_url = request.data.get("student_repo_url", "")
            if not student_id:
                raise ValidationError({"student_id": "required"})
            # Validate the student exists in the same org before linking.
            from users.models import User
            try:
                student = User.objects.get(pk=student_id)
            except User.DoesNotExist:
                raise NotFound("student not found")
            if (
                not request.user.is_superuser
                and student.organization_id != request.user.organization_id
            ):
                raise PermissionDenied("student is in a different organization")
            # OneToOne on student: one cohort per student. If the student is
            # already in a DIFFERENT cohort, block the move — Workstream B+
            # will add a proper "transfer student between cohorts" flow.
            existing = CohortMembership.objects.filter(student=student).first()
            if existing and existing.cohort_id != cohort.id:
                raise ValidationError(
                    {"student": f"student is already in cohort {existing.cohort_id}; transfer not supported in v1"}
                )
            m, created = CohortMembership.objects.update_or_create(
                student=student,
                defaults={"cohort": cohort, "student_repo_url": repo_url},
            )
            return Response(
                CohortMembershipSerializer(m).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        # DELETE
        student_id = request.query_params.get("student_id")
        if not student_id:
            raise ValidationError({"student_id": "required"})
        deleted, _ = CohortMembership.objects.filter(
            cohort=cohort, student_id=student_id
        ).delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Submission (mostly read-only for v1)
# ─────────────────────────────────────────────────────────────────────────────
class SubmissionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/grading/submissions/
    Submissions are usually created by the webhook ingest path, not via this
    endpoint. Teachers list/retrieve; students see their own.
    """

    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated, IsTeacherOrReadOnlyStudent]

    def get_queryset(self):
        user = self.request.user
        qs = Submission.objects.for_user(user).select_related(
            "course", "student"
        )
        # Filter by course if provided. Accept both `course` and legacy
        # `classroom` query params for v1 UI transition.
        course_id = self.request.query_params.get("course") or self.request.query_params.get("classroom")
        if course_id:
            qs = qs.filter(course_id=course_id)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        # Students see only their own
        role = getattr(user, "role", None)
        if role not in {"teacher", "admin"}:
            qs = qs.filter(student=user)
        return qs.order_by("-created_at")


# ─────────────────────────────────────────────────────────────────────────────
# GradingSession — the grading inbox
# ─────────────────────────────────────────────────────────────────────────────
class GradingSessionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/grading/sessions/
    The grading inbox. Teachers list/retrieve/patch; custom actions for the
    review lifecycle.
    """

    permission_classes = [IsAuthenticated, IsTeacher]

    def get_serializer_class(self):
        if self.action == "list":
            return GradingSessionListSerializer
        if self.action == "partial_update" or self.action == "update":
            return GradingSessionEditSerializer
        return GradingSessionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = GradingSession.objects.for_user(user).select_related(
            "submission",
            "submission__course",
            "submission__student",
            "rubric",
        ).prefetch_related("posted_comments")

        # Accept both `course` and legacy `classroom` query params.
        course_id = self.request.query_params.get("course") or self.request.query_params.get("classroom")
        if course_id:
            qs = qs.filter(submission__course_id=course_id)

        state = self.request.query_params.get("state")
        if state:
            qs = qs.filter(state=state)

        overdue_only = self.request.query_params.get("overdue") == "true"
        if overdue_only:
            qs = qs.filter(
                submission__due_at__lt=timezone.now(),
                state__in=[
                    GradingSession.State.PENDING,
                    GradingSession.State.DRAFTED,
                    GradingSession.State.REVIEWING,
                ],
            )

        return qs.order_by("submission__due_at", "-created_at")

    # ── custom actions ───────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="start_review")
    def start_review(self, request, pk=None):
        """
        Docent clicks into the grading session. Transition drafted → reviewing
        and start the stopwatch. Idempotent: if already reviewing, no-op.
        """
        try:
            with transaction.atomic():
                session = (
                    GradingSession.objects.for_user(request.user)
                    .select_for_update()
                    .get(pk=pk)
                )
                if session.state == GradingSession.State.REVIEWING:
                    return Response(GradingSessionDetailSerializer(session).data)
                if not session.can_transition_to(GradingSession.State.REVIEWING):
                    raise ValidationError(
                        {"state": f"cannot transition from {session.state} to reviewing"}
                    )
                session.state = GradingSession.State.REVIEWING
                if not session.docent_review_started_at:
                    session.docent_review_started_at = timezone.now()
                session.save(update_fields=["state", "docent_review_started_at", "updated_at"])
        except GradingSession.DoesNotExist:
            raise Http404

        return Response(GradingSessionDetailSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="generate_draft")
    def generate_draft(self, request, pk=None):
        """
        Kick off the rubric grader. For v1 this is synchronous; v1.1 moves it
        to a Celery/RQ worker when p95 > 8s starts biting.
        """
        from .services import rubric_grader
        from .services.pii_redaction import StudentIdentity
        from .exceptions import (
            DiffTooLargeError,
            EmptyDiffError,
            LLMCeilingExceeded,
            LLMError,
        )

        try:
            with transaction.atomic():
                session = (
                    GradingSession.objects.for_user(request.user)
                    .select_for_update()
                    .select_related("submission", "submission__student", "rubric")
                    .get(pk=pk)
                )
                if not session.can_transition_to(GradingSession.State.DRAFTING):
                    raise ValidationError(
                        {"state": f"cannot generate_draft from state={session.state}"}
                    )
                session.state = GradingSession.State.DRAFTING
                session.save(update_fields=["state", "updated_at"])
        except GradingSession.DoesNotExist:
            raise Http404

        # Release the lock before the long LLM call so other requests can
        # read the session state. We'll re-lock to write the result back.
        submission = session.submission
        student = submission.student

        # Fetch the PR diff LIVE from GitHub at grade-time so the teacher
        # sees the current state, not a stale push-evaluation snapshot.
        # Intentionally decouples grading from the push-evaluation chain
        # (see grading/services/github_fetcher.py docstring).
        from .services import github_fetcher
        from .exceptions import GitHubAuthExpired, GitHubError, PRClosedError

        combined_diff = ""
        try:
            owner, repo = submission.repo_full_name.split("/", 1)
            teacher_pat = getattr(request.user, "github_personal_access_token", None)
            combined_diff = github_fetcher.fetch_pr_diff(
                owner=owner,
                repo=repo,
                pr_number=submission.pr_number,
                token=teacher_pat,
            )
        except PRClosedError as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.FAILED
                s.save(update_fields=["state", "updated_at"])
            return Response(
                {"error": "pr_closed", "message": str(e)},
                status=status.HTTP_409_CONFLICT,
            )
        except (GitHubAuthExpired, GitHubError, ValueError) as e:
            # Fallback: if we can't fetch from GitHub, try stored evaluations.
            log.warning("generate_draft: live fetch failed, falling back: %s", e)
            for se in session.session_evaluations.select_related("evaluation").all():
                ev = se.evaluation
                combined_diff += (getattr(ev, "diff", "") or "") + "\n"

        # Resolve the org's LLM configuration from the DB so the AI engine
        # uses the school's own API key and model, not the engine env-var
        # fallback. Returns None if no config is found (engine falls back).
        from users.org_llm import get_org_llm_config
        llm_config = get_org_llm_config(request.user)

        input_ = rubric_grader.GraderInput(
            diff=combined_diff,
            rubric_criteria=session.rubric.criteria,
            rubric_calibration=session.rubric.calibration or {},
            student=StudentIdentity(
                student_id=student.id,
                display_name=student.display_name,
                first_name=student.first_name,
                email=student.email,
                github_handle=(
                    student.git_connections.filter(provider="github").values_list(
                        "username", flat=True
                    ).first()
                    or ""
                ),
                gitlab_handle=(
                    student.git_connections.filter(provider="gitlab").values_list(
                        "username", flat=True
                    ).first()
                    or ""
                ),
            ),
            context={},  # v1.1: fill with recurring-error summary etc.
            tier="premium",
            docent_id=request.user.id,
            llm_config=llm_config,
        )

        try:
            result = rubric_grader.generate_draft(
                org_id=session.org_id,
                grading_session_id=session.id,
                input_=input_,
            )
        except EmptyDiffError:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.DISCARDED
                s.save(update_fields=["state", "updated_at"])
            return Response(
                {"error": "empty_diff", "message": "Submission has no code to grade"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except LLMCeilingExceeded as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.FAILED
                s.save(update_fields=["state", "updated_at"])
            log.warning("generate_draft: ceiling exceeded for session=%s: %s", session.id, e)
            return Response(
                {"error": "ceiling_exceeded", "message": "Daily budget reached, try again tomorrow"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except (LLMError, DiffTooLargeError) as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.FAILED
                s.save(update_fields=["state", "updated_at"])
            log.warning("generate_draft failed session=%s: %s", session.id, e)
            return Response(
                {"error": "llm_failed", "message": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Persist the draft.
        with transaction.atomic():
            s = (
                GradingSession.objects.for_user(request.user)
                .select_for_update()
                .get(pk=session.id)
            )
            s.ai_draft_scores = result.scores
            s.ai_draft_comments = result.comments
            s.ai_draft_model = result.model_name
            s.ai_draft_generated_at = timezone.now()
            s.ai_draft_truncated = result.truncated
            s.state = GradingSession.State.DRAFTED
            s.save(
                update_fields=[
                    "ai_draft_scores",
                    "ai_draft_comments",
                    "ai_draft_model",
                    "ai_draft_generated_at",
                    "ai_draft_truncated",
                    "state",
                    "updated_at",
                ]
            )

        # Bind rubric scores to per-skill SkillObservation rows so the
        # student trajectory view has data. Wrapped in try/except: a skill-
        # binding failure must never fail the grading flow itself.
        try:
            from .services.skill_binding import bind_rubric_to_observations
            obs_count = bind_rubric_to_observations(s)
            log.info(
                "bound %d skill observations for session=%s", obs_count, s.id,
            )
        except Exception as e:  # defensive — never break grading on skill bind
            log.warning(
                "skill binding failed for session=%s: %s", s.id, e,
                exc_info=True,
            )

        return Response(
            {
                **GradingSessionDetailSerializer(s).data,
                "warnings": result.warnings,
            }
        )

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        """
        Post approved comments to GitHub. Real implementation (Day 7-8):
        transitions state → SENDING under select_for_update, calls
        github_poster.post_all_or_nothing() OUTSIDE the transaction
        (network I/O under row-lock is the anti-pattern), and writes the
        final state back in a short closing transaction.

        Idempotency:
          - State is SENDING before the I/O → a concurrent click sees
            SENDING and returns 202 without re-posting.
          - Each comment's client_mutation_id is checked against
            PostedComment → duplicates skip silently.
        """
        try:
            with transaction.atomic():
                session = (
                    GradingSession.objects.for_user(request.user)
                    .select_for_update()
                    .get(pk=pk)
                )
                if session.state == GradingSession.State.SENDING:
                    # idempotent double-click guard: first click already in flight
                    return Response(
                        GradingSessionDetailSerializer(session).data,
                        status=status.HTTP_202_ACCEPTED,
                    )
                if not session.can_transition_to(GradingSession.State.SENDING):
                    raise ValidationError(
                        {"state": f"cannot send from state={session.state}"}
                    )
                session.state = GradingSession.State.SENDING
                session.sending_started_at = timezone.now()
                if session.docent_review_started_at and not session.docent_review_time_seconds:
                    delta = timezone.now() - session.docent_review_started_at
                    session.docent_review_time_seconds = int(delta.total_seconds())
                session.save(
                    update_fields=[
                        "state",
                        "sending_started_at",
                        "docent_review_time_seconds",
                        "updated_at",
                    ]
                )
        except GradingSession.DoesNotExist:
            raise Http404

        # Network I/O happens OUTSIDE the transaction. The state flip above
        # already serves as the concurrency lock (SENDING → other tabs see
        # SENDING and bail). Each PostedComment row is written in its own
        # short tx inside post_all_or_nothing.
        from .services import github_poster
        from .exceptions import (
            GitHubAuthExpired,
            GitHubError,
            PartialPostError,
            PRClosedError,
        )

        teacher_pat = getattr(request.user, "github_personal_access_token", None)
        try:
            result = github_poster.post_all_or_nothing(session, teacher_pat=teacher_pat)
        except PartialPostError as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.PARTIAL
                s.partial_post_error = {
                    "error_class": type(e.inner).__name__,
                    "message": str(e.inner)[:500],
                    "failed_at_comment_idx": e.failed_at,
                    "posted_ids_so_far": e.posted_ids,
                }
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {
                    "error": "partial_post",
                    "state": s.state,
                    "failed_at_comment_idx": e.failed_at,
                    "posted_so_far": len(e.posted_ids),
                    "message": "Some comments posted; click Resume to continue.",
                },
                status=status.HTTP_207_MULTI_STATUS,
            )
        except PRClosedError as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.FAILED
                s.partial_post_error = {"error_class": "PRClosedError", "message": str(e)}
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {"error": "pr_closed", "message": str(e)},
                status=status.HTTP_409_CONFLICT,
            )
        except GitHubAuthExpired as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.DRAFTED
                s.partial_post_error = {"error_class": "GitHubAuthExpired", "message": str(e)}
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {"error": "github_auth", "message": "Re-authorize GitHub in Settings"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except GitHubError as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.FAILED
                s.partial_post_error = {"error_class": "GitHubError", "message": str(e)}
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {"error": "github_failed", "message": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            # Defensive catch-all: any non-grading exception during post_all_or_nothing
            # would otherwise leave the session stuck in SENDING forever (no
            # partial_post_error recorded, no state flip). Check how many
            # PostedComment rows actually landed on GitHub — if it equals the
            # count of comments-to-post, treat it as POSTED (the crash happened
            # in summary rendering or a post-loop step); otherwise PARTIAL so
            # the teacher can Resume.
            import logging
            log = logging.getLogger(__name__)
            log.exception("send: unexpected exception session=%s", session.id)
            from .models import PostedComment
            posted_count = PostedComment.objects.filter(grading_session=session).count()
            expected = len([c for c in (session.final_comments or session.ai_draft_comments or [])])
            all_inline_posted = posted_count >= expected and expected > 0
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                if all_inline_posted:
                    s.state = GradingSession.State.POSTED
                    s.posted_at = timezone.now()
                    s.partial_post_error = {
                        "error_class": type(e).__name__,
                        "message": f"Comments posted successfully; summary step raised: {str(e)[:300]}",
                        "recovered": True,
                    }
                    s.save(update_fields=["state", "posted_at", "partial_post_error", "updated_at"])
                    return Response(
                        {
                            "state": s.state,
                            "posted_count": posted_count,
                            "skipped_duplicate_count": 0,
                            "summary_comment_id": None,
                            "warning": "Summary comment step failed after all inline comments posted — recovered.",
                        },
                        status=status.HTTP_200_OK,
                    )
                s.state = GradingSession.State.PARTIAL
                s.partial_post_error = {
                    "error_class": type(e).__name__,
                    "message": str(e)[:500],
                    "posted_so_far": posted_count,
                }
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {
                    "error": "partial_post",
                    "state": s.state,
                    "posted_so_far": posted_count,
                    "message": "Some comments posted; click Resume to continue.",
                },
                status=status.HTTP_207_MULTI_STATUS,
            )

        # All comments (and summary) posted cleanly.
        with transaction.atomic():
            s = GradingSession.objects.select_for_update().get(pk=session.id)
            s.state = GradingSession.State.POSTED
            s.posted_at = timezone.now()
            s.partial_post_error = None
            s.save(update_fields=["state", "posted_at", "partial_post_error", "updated_at"])

        return Response(
            {
                "state": s.state,
                "posted_count": result.posted_count,
                "skipped_duplicate_count": result.skipped_duplicate_count,
                "summary_comment_id": result.summary_comment_id,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, pk=None):
        """
        Resume a partial post. Thin wrapper over the same Send path:
        github_poster's duplicate-skip IS the resume logic.
        """
        try:
            with transaction.atomic():
                session = (
                    GradingSession.objects.for_user(request.user)
                    .select_for_update()
                    .get(pk=pk)
                )
                if not session.can_transition_to(GradingSession.State.SENDING):
                    raise ValidationError(
                        {"state": f"cannot resume from state={session.state}"}
                    )
                session.state = GradingSession.State.SENDING
                session.save(update_fields=["state", "updated_at"])
        except GradingSession.DoesNotExist:
            raise Http404

        from .services import github_poster
        from .exceptions import (
            GitHubAuthExpired,
            GitHubError,
            PartialPostError,
            PRClosedError,
        )

        teacher_pat = getattr(request.user, "github_personal_access_token", None)
        try:
            result = github_poster.resume_partial(session, teacher_pat=teacher_pat)
        except PartialPostError as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.PARTIAL
                s.partial_post_error = {
                    "error_class": type(e.inner).__name__,
                    "message": str(e.inner)[:500],
                    "failed_at_comment_idx": e.failed_at,
                    "posted_ids_so_far": e.posted_ids,
                }
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {
                    "error": "partial_post",
                    "state": s.state,
                    "posted_so_far": len(e.posted_ids),
                },
                status=status.HTTP_207_MULTI_STATUS,
            )
        except (PRClosedError, GitHubAuthExpired, GitHubError) as e:
            with transaction.atomic():
                s = GradingSession.objects.select_for_update().get(pk=session.id)
                s.state = GradingSession.State.FAILED
                s.partial_post_error = {
                    "error_class": type(e).__name__,
                    "message": str(e),
                }
                s.save(update_fields=["state", "partial_post_error", "updated_at"])
            return Response(
                {"error": type(e).__name__, "message": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            s = GradingSession.objects.select_for_update().get(pk=session.id)
            s.state = GradingSession.State.POSTED
            s.posted_at = timezone.now()
            s.partial_post_error = None
            s.save(update_fields=["state", "posted_at", "partial_post_error", "updated_at"])

        return Response(
            {
                "state": s.state,
                "posted_count": result.posted_count,
                "skipped_duplicate_count": result.skipped_duplicate_count,
            },
            status=status.HTTP_200_OK,
        )

        return Response(
            {
                "state": session.state,
                "message": "Resume initiated (github_poster stub; Day 7-8).",
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# LLMCostLog — admin-internal read-only
# ─────────────────────────────────────────────────────────────────────────────
class LLMCostLogViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/grading/cost-logs/
    Admin-only read view. Teachers should not see raw cost data (privacy +
    UX: we expose an aggregate dashboard instead).
    """

    serializer_class = LLMCostLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_superuser and getattr(user, "role", None) != "admin":
            return LLMCostLog.objects.none()
        qs = LLMCostLog.objects.for_user(user).select_related("docent", "course")
        docent_id = self.request.query_params.get("docent")
        if docent_id:
            qs = qs.filter(docent_id=docent_id)
        tier = self.request.query_params.get("tier")
        if tier:
            qs = qs.filter(tier=tier)
        return qs.order_by("-occurred_at")
