"""
Project API Views
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db import models
from .models import Project, ProjectMember
from .serializers import (
    ProjectSerializer, 
    ProjectCreateSerializer,
    ProjectMemberSerializer,
    InviteMemberSerializer,
    UpdateMemberRoleSerializer,
    WebhookInfoSerializer
)
from .permissions import IsProjectMember, CanManageProjectMembers

User = get_user_model()


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
    """Get, update, or delete a project."""
    
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMember]


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
            'instructions': instructions
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
            return f'''
GitHub Webhook Setup:
1. Go to {project.repo_url}/settings/hooks/new
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
