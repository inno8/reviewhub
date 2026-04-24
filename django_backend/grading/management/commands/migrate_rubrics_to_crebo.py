"""
migrate_rubrics_to_crebo — one-shot, idempotent data migration that rewrites
any Rubric.criteria still carrying the old English 4-criterion shape
(readability, error_handling, security, testing) to the new Crebo 25604
aligned 6-criterion Dutch rubric.

Detection heuristic: a Rubric is "legacy-shaped" iff any of its criterion IDs
appear in `LEGACY_CRITERION_IDS`. Rubrics already on the Crebo shape are left
untouched — so re-running this is safe.

No schema migration needed: Rubric.criteria is a JSONField.

Usage:
    python manage.py migrate_rubrics_to_crebo --dry-run
    python manage.py migrate_rubrics_to_crebo
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from grading.models import Rubric
from grading.rubric_defaults import CREBO_RUBRIC_CRITERIA, LEGACY_CRITERION_IDS


class Command(BaseCommand):
    help = (
        "Rewrite Rubric.criteria rows that still carry the legacy English "
        "4-criterion structure to the Crebo 25604 aligned Dutch rubric."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which Rubric rows would be updated, without writing.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        # JSONField filtering in a portable way is awkward; iterate in Python.
        all_rubrics = list(Rubric.objects.all())
        total = len(all_rubrics)

        legacy: list[Rubric] = []
        for r in all_rubrics:
            criteria = r.criteria or []
            ids = {c.get("id") for c in criteria if isinstance(c, dict)}
            if ids & LEGACY_CRITERION_IDS:
                legacy.append(r)

        self.stdout.write(
            f"Scanned {total} Rubric row(s); {len(legacy)} carry legacy criteria."
        )

        if dry:
            for r in legacy:
                ids = [c.get("id") for c in (r.criteria or []) if isinstance(c, dict)]
                self.stdout.write(
                    f"  [dry-run] Rubric(id={r.id}, name={r.name!r}) "
                    f"criteria={ids} -> would become Crebo 6-criterion"
                )
            return

        if not legacy:
            self.stdout.write(self.style.SUCCESS("Nothing to migrate. All rubrics already on Crebo shape."))
            return

        # Rename legacy rubrics so the get_or_create lookup in
        # seed_e2e_grading / seed_dogfood_cohort (which now uses the
        # "... (Crebo 25604)" name) lines up with the existing row
        # instead of creating a new one alongside it.
        RENAMES = {
            "E2E MBO-4 ICT Rubric": "MBO-4 Software Developer Rubric (Crebo 25604)",
            "MBO-4 Webdev Q2 Rubric": "MBO-4 Webdev Q2 Rubric (Crebo 25604)",
        }

        updated = 0
        with transaction.atomic():
            for r in legacy:
                old_ids = [c.get("id") for c in (r.criteria or []) if isinstance(c, dict)]
                old_name = r.name
                new_name = RENAMES.get(old_name, old_name)
                r.criteria = CREBO_RUBRIC_CRITERIA
                fields = ["criteria"]
                if new_name != old_name:
                    r.name = new_name
                    fields.append("name")
                r.save(update_fields=fields)
                self.stdout.write(
                    f"  Rubric(id={r.id}, name={old_name!r}"
                    f"{' -> ' + repr(new_name) if new_name != old_name else ''}): "
                    f"{old_ids} -> Crebo 6-criterion"
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Migrated {updated} rubric(s) to Crebo 25604."
        ))
