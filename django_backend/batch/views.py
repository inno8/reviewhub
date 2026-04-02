"""
Batch Processing Views
"""
import requests
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404

from users.org_llm import org_llm_ready_for_user, get_org_llm_config

from evaluations.models import Evaluation
from evaluations.serializers import EvaluationListSerializer

from .models import BatchJob, BatchCommitResult, DeveloperProfile
from .serializers import (
    BatchJobSerializer,
    BatchJobCreateSerializer,
    BatchJobListSerializer,
    BatchCommitResultSerializer,
    DeveloperProfileSerializer
)


def notify_ai_engine_batch_start(job: BatchJob) -> None:
    """Tell the AI engine to process this job; stores error_message if the request fails."""
    try:
        fastapi_url = getattr(settings, 'FASTAPI_URL', 'http://localhost:8001')
        payload = {
            'job_id': job.id,
            'project_id': job.project_id,
            'submitter_user_id': job.user_id,
            'repo_url': job.repo_url,
            'branch': job.branch,
            'resolved_branches': list(job.resolved_branches or []),
            'target_github_username': (job.target_github_username or '').strip() or None,
            'max_commits': job.max_commits,
            'since_date': str(job.since_date) if job.since_date else None,
        }

        # Pass the org admin's LLM credentials so the AI engine uses the right provider
        llm_cfg = get_org_llm_config(job.user)
        if llm_cfg:
            payload['llm_provider'] = llm_cfg['provider']
            payload['llm_api_key'] = llm_cfg['api_key']
            payload['llm_model'] = llm_cfg['model']

        response = requests.post(
            f"{fastapi_url}/batch/start",
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        job.error_message = f"Failed to notify AI Engine: {str(e)}"
        job.save(update_fields=['error_message'])


class BatchRepoBranchesView(APIView):
    """
    GET ?repo_url=&author=
    Lists branch names from GitHub; if author is set, only branches with commits by that author.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        repo_url = (request.query_params.get('repo_url') or '').strip()
        author = (request.query_params.get('author') or '').strip()
        if not repo_url.startswith('https://github.com/'):
            return Response(
                {'detail': 'Only https://github.com/ URLs are supported.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from django.contrib.auth import get_user_model

            from .github_branches import list_active_branches

            u = get_user_model().objects.get(pk=request.user.pk)
            branches = list_active_branches(
                repo_url,
                author=author or None,
                user_token=u.github_personal_access_token,
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except requests.RequestException as e:
            return Response(
                {'detail': f'GitHub request failed: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'branches': branches})


class BatchOrgLlmCheckView(APIView):
    """
    Returns whether the current user's organisation has an admin LLM configured.
    Used by the UI before starting batch analysis.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ok, message = org_llm_ready_for_user(request.user)
        return Response({"ready": ok, "detail": message})


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

    def create(self, request, *args, **kwargs):
        ok, message = org_llm_ready_for_user(request.user)
        if not ok:
            return Response(
                {
                    "detail": message,
                    "code": "org_llm_not_configured",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Create job, link repo to project, and notify FastAPI to start processing."""
        job = serializer.save(user=self.request.user)

        if job.project_id:
            job.project.refresh_from_db()
            job.project.apply_repo_url_from_clone_url(job.repo_url)

        notify_ai_engine_batch_start(job)


class BatchJobRerunView(APIView):
    """
    Start a new batch job with the same parameters as an existing one (e.g. after prompt fixes).
    Does not reuse the create serializer (project may already be linked to a repo).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        ok, message = org_llm_ready_for_user(request.user)
        if not ok:
            return Response(
                {'detail': message, 'code': 'org_llm_not_configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source = get_object_or_404(BatchJob, pk=pk, user=request.user)
        busy_statuses = (
            BatchJob.Status.PENDING,
            BatchJob.Status.CLONING,
            BatchJob.Status.ANALYZING,
            BatchJob.Status.BUILDING_PROFILE,
        )
        if source.status in busy_statuses:
            return Response(
                {'detail': 'This batch is still active. Wait for it to finish or cancel it first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_job = BatchJob.objects.create(
            user=request.user,
            project=source.project,
            repo_url=source.repo_url,
            branch=source.branch,
            resolved_branches=list(source.resolved_branches or []),
            target_github_username=source.target_github_username,
            max_commits=source.max_commits,
            since_date=source.since_date,
        )

        if new_job.project_id:
            new_job.project.refresh_from_db()
            new_job.project.apply_repo_url_from_clone_url(new_job.repo_url)

        notify_ai_engine_batch_start(new_job)
        return Response(BatchJobSerializer(new_job).data, status=status.HTTP_201_CREATED)


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


class BatchJobEvaluationsView(generics.ListAPIView):
    """
    Evaluations created during a batch run (commit history for finished jobs).
    """

    serializer_class = EvaluationListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job_id = self.kwargs.get('job_id')
        job = get_object_or_404(
            BatchJob,
            id=job_id,
            user=self.request.user,
        )
        return (
            Evaluation.objects.filter(batch_job=job)
            .select_related('author', 'project')
            .order_by('-created_at')
        )


class DeveloperProfileView(APIView):
    """
    Get or update the current user's developer profile.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current user's profile (200 + JSON null if none yet — not a missing route)."""
        try:
            profile = request.user.developer_profile
            serializer = DeveloperProfileSerializer(profile)
            return Response(serializer.data)
        except DeveloperProfile.DoesNotExist:
            return Response(None, status=status.HTTP_200_OK)
    
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

        # Build developer profile when batch completes
        if data.get('status') == 'completed' and job.user and job.project:
            from .services import build_profile_from_batch
            try:
                build_profile_from_batch(job.user, job)
            except Exception as e:
                print(f"Failed to build profile for job {job.id}: {e}")

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
            'pending_jobs': jobs.filter(status=BatchJob.Status.PENDING).count(),
            'completed_jobs': jobs.filter(status=BatchJob.Status.COMPLETED).count(),
            'running_jobs': jobs.filter(
                status__in=[
                    BatchJob.Status.CLONING,
                    BatchJob.Status.ANALYZING,
                    BatchJob.Status.BUILDING_PROFILE
                ]
            ).count(),
            'failed_jobs': jobs.filter(status=BatchJob.Status.FAILED).count(),
            'cancelled_jobs': jobs.filter(status=BatchJob.Status.CANCELLED).count(),
            'total_commits_analyzed': sum(j.processed_commits for j in jobs),
            'total_findings': sum(j.findings_count for j in jobs),
        })
