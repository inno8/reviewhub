"""
Email utilities for LEERA / ReviewHub.

Dev: Django SMTP backend (Gmail or local mailhog).
Prod: Resend SDK when RESEND_API_KEY is set, otherwise falls back to
Django SMTP. The Resend path uses HTTPS so it bypasses SMTP-port blocks
that some hosting providers apply (e.g. DigitalOcean's outbound 25/465/587
block).

All HTML emails ship with a plain-text alternative so clients that strip
HTML (or recipients who view in a text-only client) still get the message.
"""
import logging
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Low-level transport helpers
# ─────────────────────────────────────────────────────────────────────

def _send_via_resend(
    to: str,
    subject: str,
    text: str,
    from_email: str,
    html: str | None = None,
) -> bool:
    """Send via the Resend SDK over HTTPS. Supports html + text multipart."""
    import resend

    resend.api_key = getattr(settings, 'RESEND_API_KEY', '')
    payload: dict = {
        "from": from_email,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    try:
        resend.Emails.send(payload)
        return True
    except Exception as e:
        logger.error("Resend send failed to %s: %s", to, e)
        return False


def _send_email(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    """
    Route an email through Resend (if RESEND_API_KEY is set) or Django SMTP.

    Always sends a plain-text body. If `html` is provided, the recipient
    gets a multipart/alternative message (HTML preferred, text fallback).
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@reviewhub.com')
    resend_key = getattr(settings, 'RESEND_API_KEY', '')

    if resend_key:
        return _send_via_resend(to, subject, text, from_email, html)

    try:
        msg = EmailMultiAlternatives(subject, text, from_email, [to])
        if html:
            msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error("SMTP send failed to %s: %s", to, e)
        return False


# ─────────────────────────────────────────────────────────────────────
# Branded templates
# ─────────────────────────────────────────────────────────────────────

# Design tokens — mirror the LEERA frontend palette so the email matches
# the app a recipient lands in after clicking the CTA.
_BG = "#10141a"
_SURFACE = "#181c22"
_BORDER = "rgba(139,145,157,0.15)"
_TEXT = "#dfe2eb"
_TEXT_MUTED = "#a8b0bd"
_TEXT_DIM = "#8b919d"
_PRIMARY = "#a2c9ff"
_ON_PRIMARY = "#00315c"


def _render_invitation_html(org_name: str, invite_url: str) -> str:
    """
    Branded invitation email — dark LEERA palette, Dutch copy, table-based
    layout (most reliable across email clients including Outlook).
    Inline styles only; <style> tags get stripped by Gmail/Outlook.
    """
    safe_org = escape(org_name)
    safe_url = escape(invite_url, quote=True)
    # Logo served from the public frontend nginx — same site the CTA links to.
    base_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    logo_url = f"{base_url}/logo/leera-wordmark-primary-512.png"

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Uitnodiging voor {safe_org}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};color:{_TEXT};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_BG};">
    <tr>
      <td align="center" style="padding:40px 20px;">

        <!-- Logo -->
        <img src="{logo_url}" alt="LEERA" width="120" height="auto" style="display:block;border:0;outline:none;text-decoration:none;margin-bottom:32px;max-width:120px;">

        <!-- Card -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px;margin:0 auto;background:{_SURFACE};border:1px solid {_BORDER};border-radius:16px;">
          <tr>
            <td style="padding:40px 32px;">
              <p style="margin:0 0 12px;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{_PRIMARY};font-weight:600;">UITNODIGING</p>
              <h1 style="margin:0 0 20px;font-size:24px;font-weight:700;color:{_TEXT};line-height:1.3;">
                Welkom bij {safe_org}
              </h1>

              <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:{_TEXT_MUTED};">
                <strong style="color:{_TEXT};">{safe_org}</strong> heeft je uitgenodigd om mee te doen op LEERA — Nakijken Copilot voor het MBO. Klas-niveau feedback op elke pull request, met de docent altijd in de regie.
              </p>

              <p style="margin:0 0 32px;font-size:15px;line-height:1.6;color:{_TEXT_MUTED};">
                Klik op de knop hieronder om je account in te stellen.
              </p>

              <!-- CTA -->
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 8px;">
                <tr>
                  <td style="border-radius:10px;background:{_PRIMARY};">
                    <a href="{safe_url}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:700;color:{_ON_PRIMARY};text-decoration:none;border-radius:10px;">
                      Account instellen →
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:32px 0 0;font-size:13px;line-height:1.6;color:{_TEXT_DIM};">
                Werkt de knop niet? Plak deze link in je browser:<br>
                <a href="{safe_url}" style="color:{_PRIMARY};word-break:break-all;text-decoration:underline;">{safe_url}</a>
              </p>

              <hr style="border:0;border-top:1px solid {_BORDER};margin:32px 0;">

              <p style="margin:0;font-size:12px;line-height:1.5;color:{_TEXT_DIM};">
                Deze uitnodiging verloopt over 7 dagen. Heb je deze e-mail per ongeluk ontvangen, dan kun je deze veilig negeren.
              </p>
            </td>
          </tr>
        </table>

        <!-- Footer -->
        <p style="margin:24px 0 0;font-size:11px;color:{_TEXT_DIM};letter-spacing:0.5px;">
          © 2026 LEERA · Nakijken Copilot voor het MBO
        </p>

      </td>
    </tr>
  </table>
</body>
</html>"""


def _render_invitation_text(org_name: str, invite_url: str) -> str:
    """Plain-text fallback for clients that strip or refuse HTML."""
    return (
        f"Welkom bij {org_name}\n"
        f"\n"
        f"{org_name} heeft je uitgenodigd om mee te doen op LEERA — "
        f"Nakijken Copilot voor het MBO. Klas-niveau feedback op elke "
        f"pull request, met de docent altijd in de regie.\n"
        f"\n"
        f"Klik op deze link om je account in te stellen:\n"
        f"\n"
        f"{invite_url}\n"
        f"\n"
        f"Deze uitnodiging verloopt over 7 dagen. Heb je deze e-mail per "
        f"ongeluk ontvangen, dan kun je deze veilig negeren.\n"
        f"\n"
        f"— Het LEERA team\n"
    )


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def send_invitation_email(
    email: str,
    org_name: str,
    token: str,
    invited_by: str = "",  # accepted for backward-compat; unused
):
    """
    Send a branded HTML invitation email to join an organization.

    The school (org_name) is presented as the inviting entity in the
    copy; the individual inviter's name is intentionally not surfaced
    so the recipient sees the email as coming from "the school" rather
    than from a specific staff member's email-style identity.

    `invited_by` kwarg is preserved for callers that pass it but no
    longer rendered in the email body.
    """
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    invite_url = f"{base_url}/accept-invite?token={token}"

    subject = f"Uitnodiging: kom bij {org_name} op LEERA"
    text = _render_invitation_text(org_name, invite_url)
    html = _render_invitation_html(org_name, invite_url)

    success = _send_email(email, subject, text, html=html)
    if success:
        logger.info("Invitation email sent to %s for org %s", email, org_name)
    else:
        logger.error("Failed to send invitation email to %s", email)
    return success


def send_otp_email(email: str, otp_code: str):
    """Send OTP verification code via email."""
    subject = "Je LEERA verificatiecode"
    text = (
        f"Je verificatiecode is: {otp_code}\n\n"
        f"Deze code verloopt over 15 minuten.\n\n"
        f"Heb je deze code niet aangevraagd? Negeer dan deze e-mail.\n\n"
        f"— Het LEERA team"
    )

    success = _send_email(email, subject, text)
    if success:
        logger.info("OTP email sent to %s", email)
    else:
        logger.error("Failed to send OTP email to %s", email)
    return success
