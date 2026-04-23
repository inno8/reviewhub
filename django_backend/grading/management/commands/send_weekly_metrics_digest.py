"""
`python manage.py send_weekly_metrics_digest [--email=a@x,b@y] [--days=7]`

(Named `send_weekly_metrics_digest` to avoid colliding with the existing
`send_weekly_digest` command in the evaluations app.)

Builds the same report as /api/grading/ops/metrics/weekly/ and sends it
via Django's configured email backend (console in dev, SMTP/SES in prod).

One email per org (subject includes the org name). Superuser-style "all
orgs" run sends one message per org to keep inboxes readable.

Config:
  - Recipient list: --email flag (comma-separated) OR env var
    WEEKLY_DIGEST_RECIPIENTS (comma-separated). No fallback: if neither
    is set the command logs a warning and exits 0 (idempotent, safe to
    cron).
  - Window: --days=N (default 7). Ends "today" in the server timezone.

The command mutates nothing — safe to run repeatedly.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import timezone

from ...services.metrics import compute_weekly_metrics

log = logging.getLogger(__name__)


def _parse_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


class Command(BaseCommand):
    help = "Send the weekly metrics digest email (one per org)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            dest="email",
            default=None,
            help="Comma-separated recipient list. Overrides the env var.",
        )
        parser.add_argument(
            "--days",
            dest="days",
            type=int,
            default=7,
            help="Window length in days ending today (default 7).",
        )

    def handle(self, *args, **opts):
        days = opts["days"]
        if days <= 0:
            raise CommandError("--days must be positive")

        recipients = _parse_recipients(opts.get("email")) or _parse_recipients(
            os.environ.get("WEEKLY_DIGEST_RECIPIENTS", ""),
        )
        if not recipients:
            self.stdout.write(self.style.WARNING(
                "No recipients configured (--email flag and "
                "WEEKLY_DIGEST_RECIPIENTS env var are both empty). "
                "Nothing to send.",
            ))
            return

        end = timezone.localdate()
        start = end - timedelta(days=days)

        report = compute_weekly_metrics(start, end, org_ids=None)

        orgs = report["orgs"]
        if not orgs:
            self.stdout.write(
                "No org activity in the period — sending a single summary email.",
            )
            self._send_one(
                subject=f"Weekly Report: (no activity) — week ending {end.isoformat()}",
                context={
                    "period": report["period"],
                    "org": None,
                    "grand_totals": report["grand_totals"],
                },
                recipients=recipients,
            )
            return

        for org in orgs:
            subject = (
                f"Weekly Report: {org['org_name']} "
                f"— week ending {end.isoformat()}"
            )
            self._send_one(
                subject=subject,
                context={
                    "period": report["period"],
                    "org": org,
                    "grand_totals": report["grand_totals"],
                },
                recipients=recipients,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Sent {len(orgs)} digest email(s) to {len(recipients)} recipient(s).",
        ))

    def _send_one(self, *, subject: str, context: dict, recipients: list[str]):
        text_body = render_to_string("emails/weekly_digest.txt", context)
        html_body = render_to_string("emails/weekly_digest.html", context)
        from_email = getattr(
            settings, "DEFAULT_FROM_EMAIL", "noreply@reviewhub.local",
        )
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=recipients,
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
