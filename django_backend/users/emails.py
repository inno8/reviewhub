"""
Email utilities for ReviewHub.
Dev: Gmail SMTP via Django's SMTP backend.
Prod: Resend SDK when RESEND_API_KEY is set, otherwise falls back to Django SMTP.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send_via_resend(to: str, subject: str, message: str, from_email: str) -> bool:
    """Send email using the Resend SDK (production)."""
    import resend

    resend.api_key = getattr(settings, 'RESEND_API_KEY', '')
    try:
        resend.Emails.send({
            "from": from_email,
            "to": [to],
            "subject": subject,
            "text": message,
        })
        return True
    except Exception as e:
        logger.error("Resend send failed to %s: %s", to, e)
        return False


def _send_email(to: str, subject: str, message: str) -> bool:
    """Route email through Resend (if configured) or Django SMTP."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@reviewhub.com')
    resend_key = getattr(settings, 'RESEND_API_KEY', '')

    if resend_key:
        return _send_via_resend(to, subject, message, from_email)

    # Fall back to Django SMTP (Gmail in dev)
    try:
        send_mail(subject, message, from_email, [to], fail_silently=False)
        return True
    except Exception as e:
        logger.error("SMTP send failed to %s: %s", to, e)
        return False


def send_invitation_email(email: str, org_name: str, token: str, invited_by: str = ""):
    """Send an invitation email to join an organization."""
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    invite_url = f"{base_url}/accept-invite?token={token}"

    subject = f"You're invited to join {org_name} on ReviewHub"
    message = (
        f"Hi,\n\n"
        f"{'You were invited by ' + invited_by + ' to' if invited_by else 'You are invited to'} "
        f"join {org_name} on ReviewHub — a platform that helps developers improve "
        f"their coding skills through AI-powered code review.\n\n"
        f"Click the link below to accept the invitation and set up your account:\n\n"
        f"{invite_url}\n\n"
        f"This invitation expires in 7 days.\n\n"
        f"— The ReviewHub Team"
    )

    success = _send_email(email, subject, message)
    if success:
        logger.info("Invitation email sent to %s for org %s", email, org_name)
    else:
        logger.error("Failed to send invitation email to %s", email)
    return success


def send_otp_email(email: str, otp_code: str):
    """Send OTP verification code via email."""
    subject = "Your ReviewHub verification code"
    message = (
        f"Your verification code is: {otp_code}\n\n"
        f"This code expires in 15 minutes.\n\n"
        f"If you didn't request this, please ignore this email.\n\n"
        f"— The ReviewHub Team"
    )

    success = _send_email(email, subject, message)
    if success:
        logger.info("OTP email sent to %s", email)
    else:
        logger.error("Failed to send OTP email to %s", email)
    return success
