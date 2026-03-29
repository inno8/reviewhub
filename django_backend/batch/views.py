"""
Batch Processing Views
"""
import requests
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404

from .models import BatchJob, BatchCommitResult, DeveloperProfile
from .serializers import (
    BatchJobSerializer,
    BatchJobCreateSerializer,
    BatchJobListSerializer,
    BatchCommitResultSerializer,
    DeveloperProfileSerializer
)


class BatchJobListCreateView(generics.ListCreateAPIView):
    """
    List user's batch jobs or create a new one.
    POST triggers the FastAPI AI Engine to start processing.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BatchJobCreateSerializer
        return BatchJobListSerializer
    
    def get_queryset(self):
        return BatchJob.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create job and notify FastAPI to start processing."""
        job = serializer.save(user=self.request.user)
        
        # Notify FastAPI AI Engine to start batch analysis
        try:
            fastapi_url = getattr(settings, 'FASTAPI_URL', 'http://localhost:8001')
            response = requests.post(
                f"{fastapi_url}/batch/start",
                json={
                    'job_id': job.id,
                    'repo_url': job.repo_url,
                    'branch': job.branch,
                    'target_email': job.target_email,
                    'max_commits': job.max_commits,
                    'since_date': str(job.since_date) if job.since_date else None,
                },
                timeout=5
            )
            response.raise_for_status()
        except requests.RequestException as e:
            # Don't fail the job creation, just log the error
            # Worker will pick it up later
            job.error_message = f"Failed to notify AI Engine: {str(e)}"
            job.save()


class BatchJobDetailView(generics.RetrieveDestroyAPIView):
    """
    Get batch job details or cancel it.
    """
    serializer_class = BatchJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return BatchJob.objects.filter(user=self.request.user)
    
    def perform_destroy(self, instance):
        """Cancel a running job instead of deleting."""
        if instance.is_running:
            instance.status = BatchJob.Status.CANCELLED
            instance.save()
            
            # Notify FastAPI to cancel
            try:
                fastapi_url = getattr(settings, 'FASTAPI_URL', 'http://localhost:8001')
                requests.post(
                    f"{fastapi_url}/batch/cancel",
                    json={'job_id': instance.id},
                    timeout=5
                )
            except requests.RequestException:
                pass
        else:
            instance.delete()


class BatchJobResultsView(generics.ListAPIView):
    """
    Get commit results for a batch job.
    """
    serializer_class = BatchCommitResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        job_id = self.kwargs.get('job_id')
        job = get_object_or_404(
            BatchJob,
            id=job_id,
            user=self.request.user
        )
        return BatchCommitResult.objects.filter(job=job)


class DeveloperProfileView(APIView):
    """
    Get or update the current user's developer profile.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current user's profile."""
        try:
            profile = request.user.developer_profile
            serializer = DeveloperProfileSerializer(profile)
            return Response(serializer.data)
        except DeveloperProfile.DoesNotExist:
            return Response(
                {'detail': 'No profile found. Run a batch analysis to build your profile.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
        """Trigger profile rebuild from latest batch job."""
        try:
            profile = request.user.developer_profile
            if profile.batch_job:
                profile.update_from_analysis()
                serializer = DeveloperProfileSerializer(profile)
                return Response(serializer.data)
            return Response(
                {'detail': 'No batch job found. Run a batch analysis first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DeveloperProfile.DoesNotExist:
            return Response(
                {'detail': 'No profile found.'},
                status=status.HTTP_404_NOT_FOUND
            )


class BatchJobInternalUpdateView(APIView):
    """
    Internal endpoint for FastAPI to update job status.
    Should be protected in production (API key, internal network only).
    """
    permission_classes = []  # No auth for internal calls (protect in prod!)
    
    def patch(self, request, pk):
        """Update job status from FastAPI."""
        try:
            job = BatchJob.objects.get(pk=pk)
        except BatchJob.DoesNotExist:
            return Response(
                {'detail': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data = request.data
        
        # Update allowed fields
        if 'status' in data:
            job.status = data['status']
        if 'total_commits' in data:
            job.total_commits = data['total_commits']
        if 'processed_commits' in data:
            job.processed_commits = data['processed_commits']
        if 'findings_count' in data:
            job.findings_count = data['findings_count']
        if 'skills_detected' in data:
            job.skills_detected = data['skills_detected']
        if 'patterns_detected' in data:
            job.patterns_detected = data['patterns_detected']
        if 'error_message' in data:
            job.error_message = data['error_message']
        
        # Set timestamps
        from django.utils import timezone
        if data.get('status') in ['cloning', 'analyzing', 'building_profile'] and not job.started_at:
            job.started_at = timezone.now()
        if data.get('status') in ['completed', 'failed', 'cancelled']:
            job.completed_at = timezone.now()
        
        job.save()
        
        serializer = BatchJobSerializer(job)
        return Response(serializer.data)


class BatchStatsView(APIView):
    """
    Get aggregate stats about batch processing.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        jobs = BatchJob.objects.filter(user=request.user)
        
        return Response({
            'total_jobs': jobs.count(),
            'completed_jobs': jobs.filter(status=BatchJob.Status.COMPLETED).count(),
            'running_jobs': jobs.filter(
                status__in=[
                    BatchJob.Status.CLONING,
                    BatchJob.Status.ANALYZING,
                    BatchJob.Status.BUILDING_PROFILE
                ]
            ).count(),
            'failed_jobs': jobs.filter(status=BatchJob.Status.FAILED).count(),
            'total_commits_analyzed': sum(j.processed_commits for j in jobs),
            'total_findings': sum(j.findings_count for j in jobs),
        })
