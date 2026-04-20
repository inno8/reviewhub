"""
Permissions for the grading app.

Grading is teacher-centric: the primary user is a User with role=TEACHER.
Students interact with the system via their own code pushes (webhooks) and
occasional self-service UI (connect repo, see own history).

Admin users have full visibility for support and internal dashboards.

Workstream C adds a finer-grained permission matrix:

  IsOrgAdmin         admin role (or superuser) only
  IsTeacherOrAdmin   teacher or admin (or superuser)
  IsCourseOwnerOrAdmin   admins always; teachers only if course.owner == user
  IsCohortVisible    admin in org; teacher who owns a course in the cohort;
                     student enrolled in the cohort
"""
from __future__ import annotations

from rest_framework import permissions

TEACHER_ROLES = {"teacher", "admin"}
ADMIN_ROLES = {"admin"}


def _role(user) -> str:
    return getattr(user, "role", "") or ""


def _is_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return _role(user) in ADMIN_ROLES


def _is_teacher_or_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return _role(user) in TEACHER_ROLES


class IsTeacher(permissions.BasePermission):
    """User must be authenticated and have role=teacher or admin."""

    message = "Teacher role required for this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return _is_teacher_or_admin(user)


class IsTeacherOrAdmin(IsTeacher):
    """Alias for IsTeacher with clearer name for Workstream C surfaces."""

    pass


class IsOrgAdmin(permissions.BasePermission):
    """Admin role (or superuser) required."""

    message = "Organization admin required for this action."

    def has_permission(self, request, view) -> bool:
        return _is_admin(request.user)


class IsTeacherOrReadOnlyStudent(permissions.BasePermission):
    """
    Teachers: full access.
    Students: read-only, and only to their own sessions.

    Object-level check happens in has_object_permission; list queryset
    filtering happens in the ViewSet via OrgScopedManager + role check.
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if _is_teacher_or_admin(user):
            return True
        # Students: read-only, own rows only
        if request.method not in permissions.SAFE_METHODS:
            return False
        student_id = getattr(obj, "student_id", None)
        return student_id == user.id


class IsCourseOwnerOrAdmin(permissions.BasePermission):
    """
    Admins always pass. Teachers pass only when they own the course
    (primary docent). Used for Course write actions and reassign.
    """

    message = "Only the course owner or an admin may perform this action."

    def has_permission(self, request, view) -> bool:
        return _is_teacher_or_admin(request.user)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if _is_admin(user):
            return True
        owner_id = getattr(obj, "owner_id", None)
        return owner_id == getattr(user, "id", None)


class IsCohortVisible(permissions.BasePermission):
    """
    Object permission for Cohort — caller can see the cohort if any of:
      - admin (or superuser) in the same org
      - teacher who owns a course in this cohort (primary or secondary)
      - student enrolled in this cohort via CohortMembership
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        # Cross-org: deny (the queryset should 404 before we get here, but
        # belt-and-braces).
        org_id = getattr(user, "organization_id", None)
        if org_id is None or getattr(obj, "org_id", None) != org_id:
            return False
        if _role(user) in ADMIN_ROLES:
            return True
        if _role(user) == "teacher":
            return obj.courses.filter(owner=user).exists() or obj.courses.filter(
                secondary_docent=user
            ).exists()
        # Student: enrolled in this cohort
        return obj.memberships.filter(student=user, removed_at__isnull=True).exists()
