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
    CohortMembership,
    Course,
    GradingSession,
    LLMCostLog,
    Rubric,
    Submission,
)
from .permissions import IsTeacher, IsTeacherOrReadOnlyStudent
from .serializers import (
    CohortMembershipSerializer,
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
# Course (was "Classroom")
# ─────────────────────────────────────────────────────────────────────────────
class CourseViewSet(viewsets.ModelViewSet):
    """
    /api/grading/courses/
    Teacher's courses. Teachers see their own + any where they're secondary.

    Membership is exposed on the Course endpoint for v1 backward compatibility:
    POST/DELETE on /courses/{id}/members/ creates/removes CohortMembership rows
    on the course's cohort. Migration to a proper /cohorts/{id}/members/
    endpoint lands in Workstream B+.
    """

    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsTeacher]

    def get_queryset(self):
        user = self.request.user
        base = Course.objects.for_user(user)
        # Also include courses where the user is the secondary docent
        return base.filter(
            # Primary: they own it
            #   OR secondary: they're the backup teacher
            owner=user,
        ) | base.filter(secondary_docent=user)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(org=user.organization, owner=user)

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
