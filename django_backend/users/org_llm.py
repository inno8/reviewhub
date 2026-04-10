"""
Resolve whether the current user's organisation has an admin with a usable LLM setup.

Organisation admins are:
- Team owner and team members with role owner or admin (per team the user belongs to)
- The creator of any UserCategory that lists the user as a member

Platform admins / staff with no team or category use their own LLM config for batch.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model

User = get_user_model()


def _admin_has_llm_with_model(user) -> bool:
    """True if user has at least one LLMConfiguration with credentials and a model."""
    from .models import LLMConfiguration

    for cfg in LLMConfiguration.objects.filter(user=user):
        if not (cfg.model or "").strip():
            continue
        if cfg.auth_method == LLMConfiguration.AuthMethod.OAUTH_GOOGLE:
            if cfg._oauth_refresh_token and len(bytes(cfg._oauth_refresh_token)) > 0:
                return True
            continue
        key = cfg._api_key
        if key and len(bytes(key)) > 0:
            return True
    # Legacy fields on User
    if user.has_llm_configured and (user.llm_model or "").strip():
        return True
    return False


def _organisation_admin_ids(user) -> set[int]:
    """User IDs who can supply org LLM config for this user."""
    from .models import Team, TeamMember, UserCategory

    admin_ids: set[int] = set()

    team_ids = set(
        TeamMember.objects.filter(user=user).values_list("team_id", flat=True)
    )
    team_ids.update(Team.objects.filter(owner=user).values_list("pk", flat=True))

    for tid in team_ids:
        team = Team.objects.filter(pk=tid).first()
        if not team:
            continue
        admin_ids.add(team.owner_id)
        for uid in TeamMember.objects.filter(
            team_id=tid,
            role__in=[
                TeamMember.TeamRole.OWNER,
                TeamMember.TeamRole.ADMIN,
            ],
        ).values_list("user_id", flat=True):
            admin_ids.add(uid)

    for cat in UserCategory.objects.filter(members=user):
        admin_ids.add(cat.created_by_id)

    has_org_structure = bool(team_ids) or UserCategory.objects.filter(members=user).exists()

    if not has_org_structure:
        if getattr(user, "role", None) == User.Role.ADMIN or user.is_staff:
            admin_ids.add(user.id)

    return admin_ids


def get_org_llm_config(user) -> "dict | None":
    """
    Return the first usable LLM config (provider, api_key, model) for the user's org.
    Returns None if no usable config is found.
    Used by batch views to pass credentials to the AI engine.
    """
    from .models import LLMConfiguration

    admin_ids = _organisation_admin_ids(user)
    if not admin_ids:
        return None

    admins = User.objects.filter(pk__in=admin_ids)
    for admin in admins:
        for cfg in LLMConfiguration.objects.filter(user=admin).order_by('-is_default', 'id'):
            if not (cfg.model or "").strip():
                continue
            if cfg.auth_method == LLMConfiguration.AuthMethod.OAUTH_GOOGLE:
                token = cfg.oauth_access_token
                if token:
                    return {"provider": cfg.provider, "api_key": token, "model": cfg.model}
                continue
            key = cfg.api_key
            if key:
                return {"provider": cfg.provider, "api_key": key, "model": cfg.model}

    # Legacy: user.llm_api_key / user.llm_model
    for admin in admins:
        legacy_key = getattr(admin, 'llm_api_key', None)
        legacy_model = getattr(admin, 'llm_model', None)
        legacy_provider = getattr(admin, 'llm_provider', None)
        if legacy_key and legacy_model:
            return {
                "provider": legacy_provider or "openai",
                "api_key": legacy_key,
                "model": legacy_model,
            }

    return None


def org_llm_ready_for_user(user) -> tuple[bool, str]:
    """
    Returns (True, "") if batch analysis may run for this user.

    Otherwise (False, human-readable message).
    """
    if not user or not user.is_authenticated:
        return False, "Authentication required."

    admin_ids = _organisation_admin_ids(user)
    if not admin_ids:
        return (
            False,
            "Your account is not linked to a team or group. Ask an administrator to add you "
            "to a team and configure an LLM provider (API key, token, or Google OAuth) and model for the organisation.",
        )

    admins = User.objects.filter(pk__in=admin_ids)
    for admin in admins:
        if _admin_has_llm_with_model(admin):
            return True, ""

    return (
        False,
        "No organisation administrator has configured an LLM (API key, access token, or Google OAuth) "
        "with a model. An admin must add this under Settings → LLM configuration before batch analysis can run.",
    )
