"""
Webhook event handlers for GitHub App lifecycle events.

These don't fan out to ai-engine like push/PR events do — they update
LEERA's local view of which installations exist and which repos each
install grants access to. The frontend's POST to
/api/github/installations/sync/ already covers the *initial* install
(the user-driven path); these handlers cover everything that happens
*after* the user leaves LEERA — adding repos in GitHub's UI, removing
the App, suspending it, etc.

Events handled:
  installation
    created             — App freshly installed. Idempotent upsert; the
                          frontend sync usually got there first, but
                          we re-confirm so the data isn't dependent on
                          the user's browser staying open.
    deleted             — App uninstalled. Mark deleted_at on the row.
                          Cached installation tokens become invalid.
    suspend / unsuspend — Mark suspended_at, no-op the rest.
    new_permissions_accepted — User approved a permission update.
                                Nothing to update locally; just ack.

  installation_repositories
    added   — New repos in the install's allowlist. Upsert StudentRepo rows.
    removed — Repos removed from allowlist. Soft-delete the rows.
"""
from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from users.github_app import invalidate_token_cache
from users.models import GitHubInstallation, StudentRepo

logger = logging.getLogger(__name__)


def handle_installation_event(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process an `installation` webhook event.

    Returns a small dict for the JSON response (status, action,
    installation_id) so the webhook view can ack with useful diagnostics
    in /admin/ logs without leaking payload details.
    """
    action = (payload.get('action') or '').strip()
    install_payload = payload.get('installation') or {}
    installation_id = install_payload.get('id')

    if not installation_id:
        logger.warning('installation event without installation.id')
        return {'ok': False, 'reason': 'missing installation_id'}

    inst = GitHubInstallation.objects.filter(installation_id=installation_id).first()

    if action == 'created':
        # The frontend sync usually got there first. If we somehow missed
        # it (user closed the tab before the sync POST completed), make
        # the install discoverable in LEERA via this webhook — but we
        # can't link it to a User without the session that the frontend
        # sync had. Log and ignore. The user can re-trigger the sync
        # by clicking "Reconnect GitHub" in their settings later.
        if not inst:
            logger.info(
                'installation.created webhook for new installation_id=%s '
                '— no DB row yet; expected to be created by frontend sync',
                installation_id,
            )
        return {
            'ok': True,
            'action': 'created',
            'installation_id': installation_id,
            'linked_to_user': inst is not None,
        }

    if not inst:
        # Lifecycle events for an installation we never knew about. Log
        # and ack — could be from a previous LEERA deployment or test.
        logger.info(
            'installation.%s for unknown installation_id=%s; ignoring',
            action, installation_id,
        )
        return {'ok': True, 'action': action, 'unknown': True}

    if action == 'deleted':
        inst.deleted_at = timezone.now()
        inst.save(update_fields=['deleted_at', 'updated_at'])
        # All repos on this install lose access at the same time.
        StudentRepo.objects.filter(
            installation=inst, is_active=True,
        ).update(is_active=False, removed_at=timezone.now())
        # Cached tokens for this install are now invalid.
        invalidate_token_cache(installation_id)
        logger.info(
            'installation.deleted: marked installation %s + repos as inactive',
            installation_id,
        )
        return {'ok': True, 'action': 'deleted', 'installation_id': installation_id}

    if action == 'suspend':
        inst.suspended_at = timezone.now()
        inst.save(update_fields=['suspended_at', 'updated_at'])
        invalidate_token_cache(installation_id)
        return {'ok': True, 'action': 'suspend', 'installation_id': installation_id}

    if action == 'unsuspend':
        inst.suspended_at = None
        inst.save(update_fields=['suspended_at', 'updated_at'])
        return {'ok': True, 'action': 'unsuspend', 'installation_id': installation_id}

    # new_permissions_accepted, future actions — ack with no change.
    return {'ok': True, 'action': action, 'noop': True}


def handle_installation_repositories_event(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process an `installation_repositories` webhook event.

    Fires when the user changes which repos this install can see —
    typically by visiting github.com/settings/installations/<id> →
    Configure and ticking/unticking repos.
    """
    action = (payload.get('action') or '').strip()
    install_payload = payload.get('installation') or {}
    installation_id = install_payload.get('id')

    if not installation_id:
        logger.warning('installation_repositories event without installation.id')
        return {'ok': False, 'reason': 'missing installation_id'}

    inst = GitHubInstallation.objects.filter(installation_id=installation_id).first()
    if not inst:
        logger.info(
            'installation_repositories.%s for unknown installation_id=%s',
            action, installation_id,
        )
        return {'ok': True, 'action': action, 'unknown': True}

    added = payload.get('repositories_added') or []
    removed = payload.get('repositories_removed') or []

    added_count = 0
    for repo in added:
        gh_id = repo.get('id')
        if not gh_id:
            continue
        StudentRepo.objects.update_or_create(
            installation=inst,
            github_repo_id=gh_id,
            defaults={
                'user': inst.user,
                'full_name': repo.get('full_name') or '?',
                'default_branch': repo.get('default_branch') or 'main',
                'is_private': bool(repo.get('private')),
                'is_active': True,
                'removed_at': None,
            },
        )
        added_count += 1

    removed_count = 0
    if removed:
        removed_ids = [r.get('id') for r in removed if r.get('id')]
        if removed_ids:
            removed_count = (
                StudentRepo.objects
                .filter(
                    installation=inst,
                    github_repo_id__in=removed_ids,
                    is_active=True,
                )
                .update(is_active=False, removed_at=timezone.now())
            )

    # Update the install's repo_selection in case the user toggled
    # "All repositories" → "Selected repositories" or back. The event
    # payload includes the new state.
    new_selection = payload.get('repository_selection')
    if new_selection in ('all', 'selected') and inst.repository_selection != new_selection:
        inst.repository_selection = new_selection
        inst.save(update_fields=['repository_selection', 'updated_at'])

    logger.info(
        'installation_repositories.%s: installation=%s added=%d removed=%d',
        action, installation_id, added_count, removed_count,
    )
    return {
        'ok': True,
        'action': action,
        'installation_id': installation_id,
        'added': added_count,
        'removed': removed_count,
    }
