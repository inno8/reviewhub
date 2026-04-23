"""
Regression tests for the teacher invitation flow.

Five bugs found + fixed in commit {pending}:
  #1 Invite API silently downgraded role=teacher → role=developer
  #2 Accept-invite didn't update existing-user role
  #3 Frontend dropdown missing Teacher option (covered by UI layer)
  #4 Accept-invite redirect was role-agnostic (frontend)
  #5 Invite email placeholder text (frontend copy)

This file owns #1 and #2 (backend). #3/#4/#5 are covered by Vitest.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from users.models import Invitation, Organization

User = get_user_model()


@pytest.fixture
def org(db):
    return Organization.objects.create(name="Test School", slug="test-school")


@pytest.fixture
def admin_user(db, org):
    u = User.objects.create_user(
        username="admin1", email="admin@school.com",
        password="pw123456", role="admin", organization=org,
    )
    return u


@pytest.fixture
def teacher_user(db, org):
    u = User.objects.create_user(
        username="teach1", email="teach@school.com",
        password="pw123456", role="teacher", organization=org,
    )
    return u


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def teacher_client(teacher_user):
    c = APIClient()
    c.force_authenticate(user=teacher_user)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Invite endpoint role-allowlist + permission-ladder
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestInviteRoleAllowlist:
    """Bug #1: invite API silently downgraded role=teacher to developer."""

    def test_admin_can_invite_teacher(self, admin_client, org):
        resp = admin_client.post(
            "/api/users/invite/",
            {"email": "newteach@school.com", "role": "teacher"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        inv = Invitation.objects.get(email="newteach@school.com")
        assert inv.role == "teacher"   # ← was "developer" before the fix
        assert inv.organization == org

    def test_admin_can_invite_developer(self, admin_client):
        resp = admin_client.post(
            "/api/users/invite/",
            {"email": "newstudent@school.com", "role": "developer"},
            format="json",
        )
        assert resp.status_code == 201
        assert Invitation.objects.get(email="newstudent@school.com").role == "developer"

    def test_admin_can_invite_viewer(self, admin_client):
        resp = admin_client.post(
            "/api/users/invite/",
            {"email": "newviewer@school.com", "role": "viewer"},
            format="json",
        )
        assert resp.status_code == 201
        assert Invitation.objects.get(email="newviewer@school.com").role == "viewer"

    def test_admin_cannot_invite_another_admin(self, admin_client):
        """Admins are created via org signup or /team direct-create, not invite.
        Blocks a subtle privilege-enumeration vector where 'invited admin'
        skips the password-policy checks in UserCreate."""
        resp = admin_client.post(
            "/api/users/invite/",
            {"email": "coAdmin@school.com", "role": "admin"},
            format="json",
        )
        assert resp.status_code == 400
        assert "role" in resp.data

    def test_admin_cannot_invite_unknown_role(self, admin_client):
        resp = admin_client.post(
            "/api/users/invite/",
            {"email": "wat@school.com", "role": "supergod"},
            format="json",
        )
        assert resp.status_code == 400
        assert "role" in resp.data


@pytest.mark.django_db
class TestInvitePermissionLadder:
    """Only admins can invite teachers. Teachers can only invite students/viewers."""

    def test_teacher_cannot_invite_another_teacher(self, teacher_client):
        resp = teacher_client.post(
            "/api/users/invite/",
            {"email": "peer@school.com", "role": "teacher"},
            format="json",
        )
        assert resp.status_code == 403
        assert "admin" in resp.data.get("role", "").lower()

    def test_teacher_can_invite_developer(self, teacher_client):
        resp = teacher_client.post(
            "/api/users/invite/",
            {"email": "dev@school.com", "role": "developer"},
            format="json",
        )
        assert resp.status_code == 201

    def test_teacher_can_invite_viewer(self, teacher_client):
        resp = teacher_client.post(
            "/api/users/invite/",
            {"email": "v@school.com", "role": "viewer"},
            format="json",
        )
        assert resp.status_code == 201


# ─────────────────────────────────────────────────────────────────────────────
# Accept-invite flow: role promotion on existing user
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestAcceptInviteRolePromotion:
    """Bug #2: accept-invite didn't update role on existing user."""

    def _create_invitation(self, org, role, email="pending@school.com"):
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        return Invitation.objects.create(
            organization=org,
            email=email,
            role=role,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_new_user_accept_teacher_invite_creates_as_teacher(self, db, org):
        inv = self._create_invitation(org, role="teacher", email="brand.new@school.com")
        resp = APIClient().post(
            "/api/users/accept-invite/",
            {"token": inv.token, "password": "pw123456"},
            format="json",
        )
        assert resp.status_code == 201
        user = User.objects.get(email="brand.new@school.com")
        assert user.role == "teacher"
        assert user.organization == org

    def test_existing_developer_accept_teacher_invite_promotes_to_teacher(self, db, org):
        """Bug #2 proof: prior code would leave role='developer'."""
        existing = User.objects.create_user(
            username="devdave", email="dave@school.com",
            password="pw123456", role="developer",
        )
        inv = self._create_invitation(org, role="teacher", email="dave@school.com")
        resp = APIClient().post(
            "/api/users/accept-invite/",
            {"token": inv.token, "password": "pw123456"},
            format="json",
        )
        assert resp.status_code == 201
        existing.refresh_from_db()
        assert existing.role == "teacher"   # ← was 'developer' before the fix
        assert existing.organization == org

    def test_existing_admin_is_not_demoted(self, db, org):
        """Guardrail: never demote an existing admin via an invite."""
        existing_admin_org = Organization.objects.create(
            name="Other Org", slug="other-org",
        )
        existing = User.objects.create_user(
            username="sarah", email="sarah@school.com",
            password="pw123456", role="admin", organization=existing_admin_org,
        )
        inv = self._create_invitation(org, role="teacher", email="sarah@school.com")
        resp = APIClient().post(
            "/api/users/accept-invite/",
            {"token": inv.token, "password": "pw123456"},
            format="json",
        )
        assert resp.status_code == 201
        existing.refresh_from_db()
        assert existing.role == "admin"   # preserved
        assert existing.organization == org   # but re-homed to new org

    def test_invitation_marked_accepted_after_success(self, db, org):
        inv = self._create_invitation(org, role="teacher", email="x@school.com")
        resp = APIClient().post(
            "/api/users/accept-invite/",
            {"token": inv.token, "password": "pw123456"},
            format="json",
        )
        assert resp.status_code == 201
        inv.refresh_from_db()
        assert inv.status == "accepted"
        assert inv.accepted_at is not None
