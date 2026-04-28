"""
add_level_labels_to_rubrics — idempotent data migration that adds the short
`label` field to every level in every stored Rubric.criteria JSON blob.

Why a follow-up command (instead of extending migrate_rubrics_to_crebo): the
Crebo migration has already run in every environment, and some rubrics may
have been hand-edited. We want a narrowly-scoped, idempotent pass that only
adds missing labels — it neither rewrites descriptions nor reshuffles the
criterion list.

Label source: the standard MBO-4 beheersingsniveau naming in
`grading.rubric_defaults.LEVEL_LABELS` (same 4 labels across all criteria).

Usage:
    python manage.py add_level_labels_to_rubrics --dry-run
    python manage.py add_level_labels_to_rubrics
"""
from __future__ import annotations

import copy

from django.core.management.base import BaseCommand
from django.db import transaction

from grading.models import Rubric
from grading.rubric_defaults import LEVEL_LABELS


class Command(BaseCommand):
    help = (
        "Add the short `label` field (MBO-4 beheersingsniveau naming) to "
        "every level in every stored Rubric.criteria JSON. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which Rubric rows would be updated, without writing.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        rubrics = list(Rubric.objects.all())
        total = len(rubrics)

        pending: list[tuple[Rubric, list, int]] = []  # (rubric, new_criteria, added_count)
        for r in rubrics:
            new_criteria, added = self._annotate(r.criteria or [])
            if added:
                pending.append((r, new_criteria, added))

        self.stdout.write(
            f"Scanned {total} Rubric row(s); {len(pending)} need label annotations."
        )

        if dry:
            for r, _, added in pending:
                self.stdout.write(
                    f"  [dry-run] Rubric(id={r.id}, name={r.name!r}): "
                    f"would add {added} level label(s)."
                )
            return

        if not pending:
            self.stdout.write(self.style.SUCCESS("Nothing to annotate. All levels already carry labels."))
            return

        updated = 0
        with transaction.atomic():
            for r, new_criteria, added in pending:
                r.criteria = new_criteria
                r.save(update_fields=["criteria"])
                self.stdout.write(
                    f"  Rubric(id={r.id}, name={r.name!r}): added {added} level label(s)."
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Annotated {updated} rubric(s) with level labels."
        ))

    @staticmethod
    def _annotate(criteria: list) -> tuple[list, int]:
        """Return (new_criteria, added_count). Pure — does not mutate input."""
        new = copy.deepcopy(criteria)
        added = 0
        for crit in new:
            if not isinstance(crit, dict):
                continue
            levels = crit.get("levels") or []
            for lvl in levels:
                if not isinstance(lvl, dict):
                    continue
                if lvl.get("label"):
                    continue
                score = lvl.get("score")
                label = LEVEL_LABELS.get(score)
                if label:
                    lvl["label"] = label
                    added += 1
        return new, added
