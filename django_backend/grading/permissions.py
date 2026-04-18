"""
Permissions for the grading app.

Grading is teacher-centric: the primary user is a User with role=TEACHER.
Students interact with the system via their own code pushes (webhooks) and
occasional self-service UI (connect repo, see own history).

Admin users have full visibility for support and internal dashboards.
"""
from __future__ import annotations

from rest_framework import permissions

TEACHER_ROLES = {"teacher", "admin"}


class IsTeacher(permissions.BasePermission):
    """User must be authenticated and have role=teacher or admin."""

    message = "Teacher role required for this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role = getattr(user, "role", None)
        return role in TEACHER_ROLES


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
        role = getattr(user, "role", None)
        if role in TEACHER_ROLES:
            return True
        # Students: read-only, own rows only
        if request.method not in permissions.SAFE_METHODS:
            return False
        student_id = getattr(obj, "student_id", None)
        return student_id == user.id
