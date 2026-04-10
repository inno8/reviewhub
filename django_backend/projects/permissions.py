"""
Project Permissions
"""
from django.contrib.auth import get_user_model
from rest_framework import permissions
from .models import ProjectMember

User = get_user_model()


def _is_platform_admin(user):
    """Global admin: staff/superuser or app role admin."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return getattr(user, 'role', None) == User.Role.ADMIN


class IsProjectMemberReadOrAdminWrite(permissions.BasePermission):
    """
    Project members may retrieve (GET). Only platform admins may update or delete.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if request.method not in permissions.SAFE_METHODS:
            return _is_platform_admin(request.user)
        if _is_platform_admin(request.user):
            return True
        if obj.created_by == request.user:
            return True
        return ProjectMember.objects.filter(project=obj, user=request.user).exists()


class IsProjectMember(permissions.BasePermission):
    """
    Permission check: user must be a member of the project.
    """
    
    def has_object_permission(self, request, view, obj):
        # Staff can do anything
        if request.user.is_staff:
            return True
        
        # Check if user is project creator
        if obj.created_by == request.user:
            return True
        
        # Check if user is a project member
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user
        ).exists()


class IsProjectOwnerOrAdmin(permissions.BasePermission):
    """
    Permission check: user must be owner or admin of the project.
    """
    
    def has_object_permission(self, request, view, obj):
        # Staff can do anything
        if request.user.is_staff:
            return True
        
        # Check if user is project creator
        if obj.created_by == request.user:
            return True
        
        # Check if user is owner or maintainer
        try:
            membership = ProjectMember.objects.get(
                project=obj,
                user=request.user
            )
            return membership.role in [
                ProjectMember.ProjectRole.OWNER,
                ProjectMember.ProjectRole.MAINTAINER
            ]
        except ProjectMember.DoesNotExist:
            return False


class CanManageProjectMembers(permissions.BasePermission):
    """
    Permission to manage project members.
    Only owners and maintainers can add/remove members.
    """
    
    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user.is_authenticated:
            return False
        
        # Get project ID from URL
        project_id = view.kwargs.get('pk')
        if not project_id:
            return False
        
        # Staff can do anything
        if request.user.is_staff:
            return True
        
        # For read-only requests, any member can view
        if request.method in permissions.SAFE_METHODS:
            from .models import Project
            try:
                project = Project.objects.get(pk=project_id)
                return ProjectMember.objects.filter(
                    project=project,
                    user=request.user
                ).exists() or project.created_by == request.user
            except Project.DoesNotExist:
                return False
        
        # For write operations, must be owner or maintainer
        from .models import Project
        try:
            project = Project.objects.get(pk=project_id)
            
            # Creator always has access
            if project.created_by == request.user:
                return True
            
            # Check role
            membership = ProjectMember.objects.get(
                project=project,
                user=request.user
            )
            return membership.role in [
                ProjectMember.ProjectRole.OWNER,
                ProjectMember.ProjectRole.MAINTAINER
            ]
        except (Project.DoesNotExist, ProjectMember.DoesNotExist):
            return False
