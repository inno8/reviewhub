"""
GitHub App-related API endpoints.

  GET  /api/github/install-url            — return the URL students hit to install
  GET  /api/github/installations/         — list this user's installations + repos
  POST /api/github/installations/sync     — sync a fresh install_id from GitHub

The install flow:

  Frontend: redirect the student's browser to the install URL
            (built from GITHUB_APP_SLUG)
  GitHub:   student picks repos, clicks Install
  GitHub:   redirects browser to the App's Setup URL with
            ?installation_id=<id>&setup_action=install
  Frontend: Vue route /dev-profile/connected reads installation_id
            from the URL, POSTs to /api/github/installations/sync
            with the JWT
  Backend:  upserts GitHubInstallation + fetches repos via the App
            JWT exchange, populates StudentRepo rows, returns summary
  Frontend: shows "Connected to N repos" + redirect into onboarding
"""
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .github_app import (
    GitHubAppConfigError,
    is_github_app_configured,
    list_installation_repos,
)
from .models import GitHubInstallation, StudentRepo

logger = logging.getLogger(__name__)


class InstallUrlView(APIView):
    """
    Return the public install URL the frontend should redirect students to.

    Format: https://github.com/apps/<slug>/installations/new
    Lets the frontend stay agnostic of the App's identity — slug change
    happens in env, no frontend deploy needed.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_github_app_configured():
            return Response(
                {
                    'configured': False,
                    'detail': (
                        'GitHub App is not configured on this server. '
                        'Operator must set GITHUB_APP_ID + private key.'
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        slug = (getattr(settings, 'GITHUB_APP_SLUG', '') or 'leera').strip()
        return Response({
            'configured': True,
            'install_url': f'https://github.com/apps/{slug}/installations/new',
            'manage_url_template': (
                'https://github.com/settings/installations/{installation_id}'
            ),
        })


class InstallationListView(APIView):
    """
    Return all GitHub App installations belonging to the current user,
    each with the list of repos that installation grants access to.

    Used by the dashboard "Connected GitHub" panel + the new-review picker.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        installations = (
            GitHubInstallation.objects
            .filter(user=request.user, deleted_at__isnull=True)
            .prefetch_related('repos')
        )
        payload = []
        for inst in installations:
            payload.append({
                'id': inst.id,
                'installation_id': inst.installation_id,
                'github_account_login': inst.github_account_login,
                'github_account_type': inst.github_account_type,
                'repository_selection': inst.repository_selection,
                'is_active': inst.is_active,
                'suspended_at': (
                    inst.suspended_at.isoformat()
                    if inst.suspended_at else None
                ),
                'created_at': inst.created_at.isoformat(),
                'repos': [
                    {
                        'id': r.id,
                        'github_repo_id': r.github_repo_id,
                        'full_name': r.full_name,
                        'default_branch': r.default_branch,
                        'is_private': r.is_private,
                        'is_active': r.is_active,
                    }
                    for r in inst.repos.filter(is_active=True)
                ],
            })
        return Response(payload)


class InstallationSyncView(APIView):
    """
    Sync a freshly-installed GitHub App installation into LEERA's DB.

    Called by the frontend right after GitHub redirects the user back
    to the Setup URL. Body: { installation_id }. Authenticated.

    Side effects:
      - Upserts a GitHubInstallation row owned by request.user
      - Calls GitHub `/installation/repositories` to enumerate the
        repos the install grants access to
      - Upserts StudentRepo rows + marks any previously-known repo as
        is_active=False if it's no longer in the response

    Idempotent — calling twice with the same installation_id is safe.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        installation_id = request.data.get('installation_id')
        try:
            installation_id = int(installation_id)
        except (TypeError, ValueError):
            return Response(
                {'installation_id': 'Required, must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_github_app_configured():
            return Response(
                {
                    'detail': (
                        'GitHub App is not configured on this server. '
                        'Cannot complete install sync.'
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Fetch repos via the App's installation token. This call also
        # implicitly verifies that the installation_id is valid and
        # currently active — GitHub returns 401/404 otherwise.
        try:
            repos = list_installation_repos(installation_id)
        except GitHubAppConfigError as e:
            logger.error('GitHub App config error during install sync: %s', e)
            return Response(
                {'detail': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Failed to list repos for installation %s', installation_id)
            return Response(
                {'detail': f'Could not fetch repos from GitHub: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Resolve the GitHub account this install belongs to. The
        # /installation/repositories response doesn't include the
        # installation metadata directly, so we infer from the first
        # repo's owner. If there are no repos (rare — student picked
        # zero), fall back to defaults — the webhook for the install
        # event will fill in the gaps later.
        if repos:
            owner = repos[0].get('owner') or {}
            account_id = owner.get('id') or 0
            account_login = owner.get('login') or '?'
            account_type = owner.get('type') or 'User'
        else:
            account_id = 0
            account_login = '?'
            account_type = 'User'

        # Upsert the installation row. installation_id is unique; if
        # it already exists for a different user, we update it but
        # don't reassign ownership — that'd leak repos across users.
        existing = GitHubInstallation.objects.filter(
            installation_id=installation_id
        ).first()
        if existing and existing.user_id != request.user.id:
            logger.warning(
                'User %s tried to sync installation %s already owned by user %s',
                request.user.id, installation_id, existing.user_id,
            )
            return Response(
                {'detail': 'This installation is already linked to a different LEERA account.'},
                status=status.HTTP_409_CONFLICT,
            )

        installation, created = GitHubInstallation.objects.update_or_create(
            installation_id=installation_id,
            defaults={
                'user': request.user,
                'github_account_id': account_id,
                'github_account_login': account_login,
                'github_account_type': account_type,
                # repository_selection comes from the install webhook
                # event ('all' or 'selected'); default to 'selected'
                # which is the common case
                'suspended_at': None,
                'deleted_at': None,
            },
        )

        # Upsert StudentRepo rows from the GitHub list. Mark any rows
        # not in the new list as is_active=False so they stop showing
        # up in pickers.
        seen_repo_ids: set[int] = set()
        for repo in repos:
            seen_repo_ids.add(repo['id'])
            StudentRepo.objects.update_or_create(
                installation=installation,
                github_repo_id=repo['id'],
                defaults={
                    'user': request.user,
                    'full_name': repo.get('full_name') or '?',
                    'default_branch': repo.get('default_branch') or 'main',
                    'is_private': bool(repo.get('private')),
                    'is_active': True,
                    'removed_at': None,
                },
            )

        # Soft-delete any repos that were previously linked but are no
        # longer accessible (student removed them from the install via
        # GitHub's settings).
        removed = (
            StudentRepo.objects
            .filter(installation=installation, is_active=True)
            .exclude(github_repo_id__in=seen_repo_ids)
        )
        removed.update(is_active=False, removed_at=timezone.now())

        installation.refresh_from_db()
        return Response(
            {
                'installation_id': installation.installation_id,
                'github_account_login': installation.github_account_login,
                'created': created,
                'repo_count': len(repos),
                'repos': [
                    {
                        'github_repo_id': r['id'],
                        'full_name': r.get('full_name'),
                    }
                    for r in repos
                ],
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
