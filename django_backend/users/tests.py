"""
Tests for ReviewHub users app — org signup, invitations, email.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import User, Organization, Invitation


# ── P2-1: Organization model ─────────────────────────────────────────────

class TestOrganizationModel(TestCase):
    """P2-1: Organization model works with proper ownership."""

    def test_org_creation(self):
        user = User.objects.create_user(
            email="admin@school.com", username="admin", password="testpass123"
        )
        org = Organization.objects.create(name="Test School", slug="test-school", owner=user)
        self.assertEqual(org.name, "Test School")
        self.assertEqual(org.owner, user)

    def test_org_slug_unique(self):
        user = User.objects.create_user(
            email="admin@school.com", username="admin", password="testpass123"
        )
        Organization.objects.create(name="School A", slug="school-a", owner=user)
        with self.assertRaises(Exception):
            Organization.objects.create(name="School A Dup", slug="school-a", owner=user)


# ── P2-2: Org self-service signup ─────────────────────────────────────────

class TestOrgSignup(TestCase):
    """P2-2: Self-service org signup creates org + admin + membership."""

    def test_org_signup_success(self):
        client = APIClient()
        response = client.post("/api/users/org-signup/", data={
            "org_name": "Code Bootcamp",
            "admin_email": "founder@bootcamp.com",
            "admin_password": "securepass123",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()

        # Org created
        self.assertIn("organization", data)
        self.assertEqual(data["organization"]["name"], "Code Bootcamp")

        # User created with admin role
        self.assertIn("user", data)
        self.assertEqual(data["user"]["role"], "admin")

        # Tokens provided
        self.assertIn("tokens", data)
        self.assertIn("access", data["tokens"])

        # User is org owner
        org = Organization.objects.get(slug="code-bootcamp")
        self.assertEqual(org.owner.email, "founder@bootcamp.com")

    def test_org_signup_duplicate_name(self):
        client = APIClient()
        client.post("/api/users/org-signup/", data={
            "org_name": "Unique School",
            "admin_email": "admin1@school.com",
            "admin_password": "securepass123",
        }, format="json")

        response = client.post("/api/users/org-signup/", data={
            "org_name": "Unique School",
            "admin_email": "admin2@school.com",
            "admin_password": "securepass123",
        }, format="json")

        self.assertEqual(response.status_code, 400)

    def test_org_signup_missing_fields(self):
        client = APIClient()
        response = client.post("/api/users/org-signup/", data={}, format="json")
        self.assertEqual(response.status_code, 400)


# ── P2-3: Student invitation system ──────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestInvitationFlow(TestCase):
    """P2-3: Admin invites student → student accepts → joins org."""

    def setUp(self):
        # Create org + admin
        self.org = Organization.objects.create(name="Test Academy", slug="test-academy")
        self.admin = User.objects.create_user(
            email="admin@academy.com", username="adminacademy",
            password="adminpass123", role="admin", organization=self.org,
        )
        self.org.owner = self.admin
        self.org.save(update_fields=["owner"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_invite_creates_pending_invitation(self):
        response = self.client.post("/api/users/invite/", data={
            "email": "student@school.com",
            "role": "developer",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.json()["status"], "pending")

        invitation = Invitation.objects.get(email="student@school.com")
        self.assertEqual(invitation.status, "pending")
        self.assertEqual(invitation.organization, self.org)

    def test_invite_sends_email(self):
        from django.core import mail

        self.client.post("/api/users/invite/", data={
            "email": "newstudent@school.com",
        }, format="json")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newstudent@school.com", mail.outbox[0].to)
        self.assertIn("Test Academy", mail.outbox[0].subject)

    def test_accept_invite_creates_user(self):
        # Admin invites
        response = self.client.post("/api/users/invite/", data={
            "email": "new@student.com",
        }, format="json")
        token = Invitation.objects.get(email="new@student.com").token

        # Student accepts (unauthenticated)
        anon_client = APIClient()
        accept_resp = anon_client.post("/api/users/accept-invite/", data={
            "token": token,
            "password": "studentpass123",
            "username": "newstudent",
        }, format="json")

        self.assertEqual(accept_resp.status_code, 201, accept_resp.data)

        # User created and in org
        student = User.objects.get(email="new@student.com")
        self.assertEqual(student.organization, self.org)
        self.assertEqual(student.role, "developer")

        # Invitation marked accepted
        invitation = Invitation.objects.get(email="new@student.com")
        self.assertEqual(invitation.status, "accepted")

    def test_accept_invite_invalid_token(self):
        anon_client = APIClient()
        response = anon_client.post("/api/users/accept-invite/", data={
            "token": "bogus-token",
            "password": "somepass123",
        }, format="json")
        self.assertEqual(response.status_code, 400)


# ── P2-4: Email sends OTP ────────────────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEmailSendsOTP(TestCase):
    """P2-4: Email system actually sends OTP codes."""

    def test_otp_email_sent(self):
        from users.emails import send_otp_email
        from django.core import mail

        result = send_otp_email("user@test.com", "12345")
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("12345", mail.outbox[0].body)
        self.assertIn("user@test.com", mail.outbox[0].to)
