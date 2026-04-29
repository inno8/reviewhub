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

    # ── New multi-tenant org model (Nakijken Copilot v1) ──────────────────
    # All admins + the owner in the same Organization can supply LLM config.
    org_id = getattr(user, "organization_id", None)
    if org_id:
        from .models import Organization
        org = Organization.objects.filter(pk=org_id).first()
        if org and org.owner_id:
            admin_ids.add(org.owner_id)
        org_admin_ids = (
            User.objects.filter(organization_id=org_id, role=User.Role.ADMIN)
            .values_list("pk", flat=True)
        )
        admin_ids.update(org_admin_ids)

    # ── Legacy: Team / UserCategory admin resolution ──────────────────────
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

    # ── Self fallback ────────────────────────────────────────────────────
    # If the user is themselves an admin (org admin OR platform staff/
    # superuser) and they have their own LLMConfiguration, allow them to
    # use it. Covers two common cases that the org-admin-only model
    # would otherwise block:
    #   * The org owner submitting a batch (they ARE the admin; the
    #     branch above already adds them via the org-owner lookup, but
    #     this catches edge cases like role mismatch on legacy accounts).
    #   * A platform superuser with their own LLM key (used during
    #     dogfood + demos before per-school admins are paying).
    # Non-admin students still fall through this block — billing model
    # intact: students can't bring their own LLM to bypass the school's
    # admin config.
    is_admin_role = getattr(user, "role", None) == User.Role.ADMIN
    is_platform_admin = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    if (is_admin_role or is_platform_admin) and user.id not in admin_ids:
        admin_ids.add(user.id)

    return admin_ids


def _platform_llm_config() -> "dict | None":
    """
    Platform-level LLM fallback. LEERA pays for LLM and schools that
    haven't configured their own use these env-vars as the floor:
        LLM_PROVIDER  (e.g. "anthropic", "openai")
        LLM_API_KEY   (the key — required)
        LLM_MODEL     (e.g. "claude-3-5-haiku-20241022")
    Returns None if any of the three is missing/empty.

    Schools that DO configure per-org LLM via Settings → LLM Config
    take precedence; this is only used when no usable per-org config
    is found.
    """
    from django.conf import settings

    provider = getattr(settings, 'PLATFORM_LLM_PROVIDER', '') or ''
    api_key = getattr(settings, 'PLATFORM_LLM_API_KEY', '') or ''
    model = getattr(settings, 'PLATFORM_LLM_MODEL', '') or ''

    if not (api_key and model):
        return None
    return {
        'provider': provider or 'anthropic',
        'api_key': api_key,
        'model': model,
    }


def get_org_llm_config(user) -> "dict | None":
    """
    Return the first usable LLM config (provider, api_key, model) for the user's org.
    Returns None if no usable config is found.
    Used by batch views to pass credentials to the AI engine.

    Resolution order:
      1. Per-user LLMConfiguration belonging to the user's org admins
      2. Legacy User.llm_api_key on those same admins
      3. Platform-level env-var fallback (PLATFORM_LLM_*) — LEERA's
         own keys, used when no school admin has configured their own
    """
    from .models import LLMConfiguration

    admin_ids = _organisation_admin_ids(user)
    admins = User.objects.filter(pk__in=admin_ids) if admin_ids else User.objects.none()

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

    # Platform-level fallback — the LEERA business-model floor.
    return _platform_llm_config()


def org_llm_ready_for_user(user) -> tuple[bool, str]:
    """
    Returns (True, "") if batch analysis may run for this user.

    Otherwise (False, human-readable message).

    The check passes if EITHER:
      - An organisation admin reachable from this user has a usable
        LLMConfiguration (per-school BYO-LLM model), OR
      - The platform-level PLATFORM_LLM_* env vars are set (LEERA-pays
        model — the floor, used when schools haven't configured their own).
    """
    if not user or not user.is_authenticated:
        return False, "Authentication required."

    # Per-school admin LLM (preferred when set).
    admin_ids = _organisation_admin_ids(user)
    if admin_ids:
        admins = User.objects.filter(pk__in=admin_ids)
        for admin in admins:
            if _admin_has_llm_with_model(admin):
                return True, ""

    # Platform-level fallback — LEERA's own keys.
    if _platform_llm_config() is not None:
        return True, ""

    return (
        False,
        "No LLM has been configured. Either an organisation admin must "
        "add a key + model under Settings → LLM Configuration, or the "
        "platform operator must set LLM_PROVIDER / LLM_API_KEY / LLM_MODEL "
        "in the deployment environment.",
    )
