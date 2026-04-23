"""
OrgScopedManager — security boundary for the grading app.

CEO review / outside-voice flagged cross-org leakage (threat #1) as the most
important correctness bet in the grading app. This manager enforces it at the
ORM level, not in the ViewSet, so it is hard to bypass by accident.

Every ViewSet in grading/views.py MUST use `.for_user(request.user)` as its
base queryset. A unit test per endpoint verifies that a user in org A cannot
read or mutate a resource in org B.
"""
from django.db import models


class OrgScopedQuerySet(models.QuerySet):
    """
    QuerySet that knows how to filter by the requesting user's organization.

    Superusers see everything. Everyone else sees only their org's rows.
    Unauthenticated callers should never reach this; views should reject
    them before the ORM is hit.
    """

    def for_user(self, user):
        if user is None or not user.is_authenticated:
            return self.none()
        if getattr(user, "is_superuser", False):
            return self
        org_id = getattr(user, "organization_id", None)
        if org_id is None:
            return self.none()
        return self.filter(org_id=org_id)


class OrgScopedManager(models.Manager.from_queryset(OrgScopedQuerySet)):
    """Manager that exposes for_user() to ViewSets."""

    pass
