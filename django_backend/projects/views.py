"""
Project API Views
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Project, ProjectMember
from .serializers import (
    ProjectSerializer, 
    ProjectCreateSerializer,
    ProjectMemberSerializer,
    WebhookInfoSerializer
)


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
    permission_classes = [permissions.IsAuthenticated]


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


class ProjectMemberListView(generics.ListCreateAPIView):
    """List and add project members."""
    
    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ProjectMember.objects.filter(project_id=self.kwargs['pk'])


# Import models at module level to avoid circular import
from django.db import models
