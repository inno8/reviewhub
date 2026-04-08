"""
Project API Views
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.shortcuts import get_object_or_404

from users.models import TeamMember
from .models import Project, ProjectMember
from .serializers import (
    ProjectSerializer, 
    ProjectCreateSerializer,
    ProjectMemberSerializer,
    InviteMemberSerializer,
    UpdateMemberRoleSerializer,
    WebhookInfoSerializer
)
from .permissions import IsProjectMemberReadOrAdminWrite, CanManageProjectMembers

User = get_user_model()


def _user_can_access_project_for_link(user, project) -> bool:
    if user.role == 'admin' or getattr(user, 'is_staff', False):
        return True
    if project.created_by_id == user.id:
        return True
    if ProjectMember.objects.filter(project=project, user=user).exists():
        return True
    if project.team_id and TeamMember.objects.filter(team_id=project.team_id, user=user).exists():
        return True
    return False


class ProjectListCreateView(generics.ListCreateAPIView):
    """List and create projects."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProjectCreateSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        """Return projects the user has access to."""
        user = self.request.user
        
        # Get projects where user is a member or creator
        return Project.objects.filter(
            models.Q(created_by=user) |
            models.Q(members__user=user) |
            models.Q(team__members__user=user)
        ).distinct()


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a project (members read; only admins may update/delete)."""

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMemberReadOrAdminWrite]


class ProjectLinkRepoView(APIView):
    """
    PATCH /projects/{pk}/link-repo/
    Lets a developer link a repository URL to an unlinked project.
    Parses provider / repo_owner / repo_name from the URL automatically.
    """

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

        if not _user_can_access_project_for_link(request.user, project):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        repo_url = (request.data.get('repo_url') or '').strip()
        if not repo_url:
            return Response({'error': 'repo_url is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Detect provider from URL
        provider = 'github'
        if 'gitlab' in repo_url:
            provider = 'gitlab'
        elif 'bitbucket' in repo_url:
            provider = 'bitbucket'

        # Parse owner / repo from URL: https://github.com/owner/repo[.git]
        try:
            from urllib.parse import urlparse
            parts = urlparse(repo_url).path.strip('/').rstrip('.git').split('/')
            repo_owner = parts[-2] if len(parts) >= 2 else project.repo_owner
            repo_name = parts[-1] if len(parts) >= 1 else project.repo_name
        except Exception:
            repo_owner = project.repo_owner or request.user.username
            repo_name = project.repo_name or project.name.lower().replace(' ', '-')

        project.repo_url = repo_url
        project.provider = provider
        project.repo_owner = repo_owner
        project.repo_name = repo_name
        project.save(update_fields=['repo_url', 'provider', 'repo_owner', 'repo_name', 'updated_at'])

        from projects.serializers import ProjectSerializer as PS
        return Response(PS(project).data)


class ProjectUnlinkRepoView(APIView):
    """
    POST /projects/{pk}/unlink-repo/
    Removes the Git repository link from the project and permanently deletes the
    current user's evaluations, findings, skill metrics, patterns, batch jobs, and
    related notifications for this project only. Other members' data is untouched.
    This operation is not reversible.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        if not _user_can_access_project_for_link(request.user, project):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        if user.role == 'admin' or getattr(user, 'is_staff', False):
            return Response(
                {'detail': 'Unlinking is only available to developers, not administrators.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not (project.repo_url or '').strip():
            return Response(
                {'detail': 'This project has no linked repository.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            eval_filter = models.Q(author=user) | models.Q(
                author__isnull=True,
                author_email__iexact=user.email,
            )
            eval_qs = project.evaluations.filter(eval_filter)
            eval_ids = list(eval_qs.values_list('id', flat=True))

            if eval_ids:
                from notifications.models import Notification

                Notification.objects.filter(
                    user=user,
                    data__evaluation_id__in=eval_ids,
                ).delete()
                eval_qs.delete()

            from skills.models import SkillMetric
            from evaluations.models import Pattern

            SkillMetric.objects.filter(user=user, project=project).delete()
            Pattern.objects.filter(user=user, project=project).delete()

            from batch.models import BatchJob

            BatchJob.objects.filter(user=user, project=project).delete()

            project.repo_url = None
            project.repo_owner = 'unlinked'
            project.repo_name = f'p{project.pk}'
            project.webhook_active = False
            project.save(
                update_fields=[
                    'repo_url',
                    'repo_owner',
                    'repo_name',
                    'webhook_active',
                    'updated_at',
                ]
            )

        from projects.serializers import ProjectSerializer as PS

        return Response(PS(project).data, status=status.HTTP_200_OK)


class ProjectWebhookView(APIView):
    """Get webhook setup information for a project."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk):
        """Get webhook URL and secret."""
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate instructions based on provider
        instructions = self._get_instructions(project)
        
        return Response({
            'webhook_url': project.webhook_url,
            'webhook_secret': project.webhook_secret,
            'provider': project.provider,
            # Our side has URL + secret (ready to paste into Git host)
            'connected': bool(project.webhook_secret and project.webhook_url),
            # True once Django has marked the project as having received a webhook delivery
            'receiving_webhooks': bool(project.webhook_active),
            'webhook_active': project.webhook_active,
            'default_branch': project.default_branch,
            'repo_url': project.repo_url,
            'instructions': instructions,
        })
    
    def post(self, request, pk):
        """Regenerate webhook secret."""
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_secret = project.regenerate_webhook_secret()
        
        return Response({
            'webhook_url': project.webhook_url,
            'webhook_secret': new_secret,
            'message': 'Webhook secret regenerated'
        })
    
    def _get_instructions(self, project):
        """Get setup instructions for provider."""
        if project.provider == 'github':
            base = project.repo_url or '(your repository URL)'
            return f'''
GitHub Webhook Setup:
1. Go to {base}/settings/hooks/new
2. Payload URL: {project.webhook_url}
3. Content type: application/json
4. Secret: {project.webhook_secret}
5. Events: Select "Just the push event"
6. Click "Add webhook"
'''
        elif project.provider == 'gitlab':
            return f'''
GitLab Webhook Setup:
1. Go to Settings → Webhooks
2. URL: {project.webhook_url}
3. Secret token: {project.webhook_secret}
4. Trigger: Push events
5. Click "Add webhook"
'''
        else:
            return 'See provider documentation for webhook setup.'


class ProjectWebhookRegisterView(APIView):
    """Auto-register a webhook on the Git provider for this project."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        if not _user_can_access_project_for_link(request.user, project):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        if not project.repo_url:
            return Response(
                {'error': 'Link a repository first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if project.provider != 'github':
            return Response(
                {'error': 'Auto-registration is currently supported for GitHub only.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from batch.webhook_setup import register_github_webhook
        result = register_github_webhook(project, request.user)

        if result.get('success'):
            project.webhook_active = True
            project.save(update_fields=['webhook_active'])

        return Response(result, status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)


class ProjectWebhookTestView(APIView):
    """Test webhook connectivity for a project."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

        connected = bool(project.webhook_secret and project.webhook_url)
        return Response({
            'connected': connected,
            'message': 'Webhook is configured and ready' if connected else 'Webhook not yet configured',
        })


class ProjectMemberListView(APIView):
    """List and add project members."""
    
    permission_classes = [permissions.IsAuthenticated, CanManageProjectMembers]
    
    def get(self, request, pk):
        """List all members of a project."""
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        members = ProjectMember.objects.filter(project=project).select_related('user')
        serializer = ProjectMemberSerializer(members, many=True)
        return Response(serializer.data)
    
    def post(self, request, pk):
        """Invite a member to the project by email."""
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = InviteMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        role = serializer.validated_data['role']
        git_email = serializer.validated_data.get('git_email', '')
        git_username = serializer.validated_data.get('git_username', '')
        
        # Get user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found with this email'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already a member
        if ProjectMember.objects.filter(project=project, user=user).exists():
            return Response(
                {'error': 'User is already a member of this project'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create membership
        member = ProjectMember.objects.create(
            project=project,
            user=user,
            role=role,
            git_email=git_email or user.email,
            git_username=git_username or user.username
        )
        
        result_serializer = ProjectMemberSerializer(member)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class ProjectMemberDetailView(APIView):
    """Update or remove a project member."""
    
    permission_classes = [permissions.IsAuthenticated, CanManageProjectMembers]
    
    def patch(self, request, pk, user_id):
        """Update member role."""
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            member = ProjectMember.objects.get(project=project, user_id=user_id)
        except ProjectMember.DoesNotExist:
            return Response(
                {'error': 'Member not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UpdateMemberRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        member.role = serializer.validated_data['role']
        member.save(update_fields=['role'])
        
        result_serializer = ProjectMemberSerializer(member)
        return Response(result_serializer.data)
    
    def delete(self, request, pk, user_id):
        """Remove a member from the project."""
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            member = ProjectMember.objects.get(project=project, user_id=user_id)
        except ProjectMember.DoesNotExist:
            return Response(
                {'error': 'Member not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Prevent removing the project creator
        if project.created_by_id == user_id:
            return Response(
                {'error': 'Cannot remove project creator'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        member.delete()
        return Response(
            {'message': 'Member removed successfully'},
            status=status.HTTP_200_OK
        )
