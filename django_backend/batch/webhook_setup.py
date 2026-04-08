"""
Webhook auto-registration for batch repos.

After a batch analysis completes, this module registers a GitHub webhook
on the repository so future pushes automatically trigger code review.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests
from django.conf import settings

from projects.models import Project

logger = logging.getLogger(__name__)


def _get_github_token(user) -> Optional[str]:
    """Get the best available GitHub token for API calls."""
    pat = getattr(user, 'github_personal_access_token', None)
    if pat:
        return pat
    return (getattr(settings, 'GITHUB_TOKEN', None) or '').strip() or None


def _webhook_callback_url(project: Project) -> Optional[str]:
    """
    Build the public callback URL for the webhook.
    Uses WEBHOOK_BASE_URL env var (typically an ngrok URL) or falls back to FASTAPI_URL.
    """
    import os
    base = (os.getenv('WEBHOOK_BASE_URL') or '').strip()
    if not base:
        base = getattr(settings, 'FASTAPI_URL', 'http://localhost:8001')
    base = base.rstrip('/')
    return f"{base}/api/v1/webhook/{project.provider}/{project.id}"


def register_github_webhook(project: Project, user) -> dict:
    """
    Register a webhook on a GitHub repository.

    Returns a dict with 'success', 'message', and optionally 'hook_id'.
    """
    token = _get_github_token(user)
    if not token:
        return {
            'success': False,
            'message': 'No GitHub token available. Add a Personal Access Token in Settings.',
        }

    owner = project.repo_owner
    repo = project.repo_name
    if not owner or not repo:
        return {
            'success': False,
            'message': 'Project missing repo_owner or repo_name.',
        }

    callback_url = _webhook_callback_url(project)
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }

    # Check if a webhook already exists for this URL
    try:
        existing = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/hooks',
            headers=headers,
            timeout=15,
        )
        if existing.status_code == 200:
            for hook in existing.json():
                config = hook.get('config', {})
                if config.get('url', '').rstrip('/') == callback_url.rstrip('/'):
                    logger.info(
                        'Webhook already exists for %s/%s (hook_id=%s)',
                        owner, repo, hook['id'],
                    )
                    return {
                        'success': True,
                        'message': 'Webhook already registered.',
                        'hook_id': hook['id'],
                        'already_existed': True,
                    }
    except requests.RequestException:
        pass  # Continue to try creating

    # Create the webhook
    payload = {
        'name': 'web',
        'active': True,
        'events': ['push'],
        'config': {
            'url': callback_url,
            'content_type': 'json',
            'secret': project.webhook_secret,
            'insecure_ssl': '0',
        },
    }

    try:
        resp = requests.post(
            f'https://api.github.com/repos/{owner}/{repo}/hooks',
            headers=headers,
            json=payload,
            timeout=15,
        )

        if resp.status_code in (201, 200):
            hook_data = resp.json()
            logger.info(
                'Webhook registered for %s/%s (hook_id=%s)',
                owner, repo, hook_data.get('id'),
            )
            return {
                'success': True,
                'message': 'Webhook registered successfully.',
                'hook_id': hook_data.get('id'),
            }
        elif resp.status_code == 404:
            return {
                'success': False,
                'message': (
                    'Repository not found or insufficient permissions. '
                    'Ensure your GitHub token has "admin:repo_hook" scope.'
                ),
            }
        elif resp.status_code == 422:
            # Often means webhook already exists or validation error
            errors = resp.json().get('errors', [])
            for err in errors:
                if 'already exists' in str(err).lower():
                    return {
                        'success': True,
                        'message': 'Webhook already registered.',
                        'already_existed': True,
                    }
            return {
                'success': False,
                'message': f'GitHub validation error: {resp.json().get("message", resp.text)}',
            }
        else:
            return {
                'success': False,
                'message': f'GitHub API error ({resp.status_code}): {resp.text[:200]}',
            }
    except requests.RequestException as e:
        logger.exception('Failed to register webhook for %s/%s', owner, repo)
        return {
            'success': False,
            'message': f'Request failed: {str(e)}',
        }
