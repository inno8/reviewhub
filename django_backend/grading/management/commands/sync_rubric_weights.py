"""
sync_rubric_weights — idempotent data migration that rewrites the `weight`
field on each criterion for every Rubric already on the 6-criterion Crebo
shape.

Context: v1 shipped with every criterion at `weight: 1.0` which caused the
frontend percentage renderer (weight / sum * 100) to produce 6 × 17% = 102%
with rounding drift. The new pedagogically-defensible weights come from
rubric_defaults.CREBO_RUBRIC_CRITERIA and sum to exactly 100.

Detection: a Rubric is in-scope iff the set of criterion IDs matches the
canonical Crebo id set. Legacy-shaped rubrics are skipped — run
`migrate_rubrics_to_crebo` first for those.

Idempotency: rubrics whose weights already match the target values are
skipped (reported as unchanged).

Usage:
    python manage.py sync_rubric_weights --dry-run
    python manage.py sync_rubric_weights
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from grading.models import Rubric
from grading.rubric_defaults import CREBO_RUBRIC_CRITERIA


CREBO_IDS = {c["id"] for c in CREBO_RUBRIC_CRITERIA}
TARGET_WEIGHTS: dict[str, int | float] = {
    c["id"]: c["weight"] for c in CREBO_RUBRIC_CRITERIA
}


class Command(BaseCommand):
    help = (
        "Rewrite the `weight` field on each criterion for Crebo-shaped "
        "Rubric rows so the sum is exactly 100. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which Rubric rows would be updated, without writing.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        all_rubrics = list(Rubric.objects.all())
        total = len(all_rubrics)

        in_scope: list[Rubric] = []
        for r in all_rubrics:
            criteria = r.criteria or []
            ids = {c.get("id") for c in criteria if isinstance(c, dict)}
            if ids == CREBO_IDS:
                in_scope.append(r)

        self.stdout.write(
            f"Scanned {total} Rubric row(s); {len(in_scope)} on Crebo 6-criterion shape."
        )

        to_update: list[tuple[Rubric, list[dict]]] = []
        unchanged = 0
        for r in in_scope:
            new_criteria: list[dict] = []
            changed = False
            for c in r.criteria:
                if not isinstance(c, dict):
                    new_criteria.append(c)
                    continue
                cid = c.get("id")
                target = TARGET_WEIGHTS.get(cid)
                if target is None:
                    new_criteria.append(c)
                    continue
                if c.get("weight") != target:
                    changed = True
                new_criteria.append({**c, "weight": target})
            if changed:
                to_update.append((r, new_criteria))
            else:
                unchanged += 1

        self.stdout.write(
            f"  {len(to_update)} rubric(s) need weight updates; "
            f"{unchanged} already match target."
        )

        if dry:
            for r, new_criteria in to_update:
                old_pairs = [(c.get("id"), c.get("weight")) for c in r.criteria if isinstance(c, dict)]
                new_pairs = [(c.get("id"), c.get("weight")) for c in new_criteria if isinstance(c, dict)]
                self.stdout.write(
                    f"  [dry-run] Rubric(id={r.id}, name={r.name!r}) "
                    f"{old_pairs} -> {new_pairs}"
                )
            return

        if not to_update:
            self.stdout.write(self.style.SUCCESS("Nothing to update."))
            return

        updated = 0
        with transaction.atomic():
            for r, new_criteria in to_update:
                r.criteria = new_criteria
                r.save(update_fields=["criteria"])
                self.stdout.write(
                    f"  Rubric(id={r.id}, name={r.name!r}): weights synced "
                    f"(sum={sum(c.get('weight', 0) for c in new_criteria if isinstance(c, dict))})"
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Synced weights on {updated} rubric(s) to Crebo targets."
        ))
