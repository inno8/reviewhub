"""
seed_demo_learning_proofs — populate LearningProof rows for the dogfood cohort
so the pitch demo shows PROVEN / PENDING / RELAPSED / REINFORCED dots in the
per-criterion breakdown.

**Why this is a separate "demo" seeder, not part of the main flow**

The new Nakijken Copilot (Crebo) grading flow does not yet wire the send-time
creation or next-PR verification of LearningProofs — that's scoped for a
post-pitch 3-5 day integration (Phases 1-3). In the meantime, the UI surface
is ready (see `per_skill[].learning_proof_status` in StudentSnapshotView) but
the table is empty for seeded students. This command creates plausible
placeholder data anchored to real Skill rows + synthetic Finding + Evaluation
rows so the dots light up during the May 7 Portfolio Day pitch.

**Idempotent**: re-running only creates missing rows, never duplicates.
**Reversible**: `--wipe` deletes everything this command created (marked via
concept_summary prefix "[demo-seed]").

Usage:
    python manage.py seed_demo_learning_proofs          # create
    python manage.py seed_demo_learning_proofs --wipe   # reset + recreate
    python manage.py seed_demo_learning_proofs --dry-run

Creates LearningProofs for the 5 Webdev Q2 2026 students with per-student
archetypes so the pitch narrative works across personas:

- Kai Nguyen  (struggler): veiligheid RELAPSED, testen PENDING, verbetering TAUGHT
- Sanne Bakker (weak on tests): testen RELAPSED, samenwerking PROVEN
- Lucas van Dijk: veiligheid PROVEN, testen PROVEN
- Jan de Boer: code_kwaliteit REINFORCED, samenwerking PROVEN
- Fatima el Amrani (strong): code_ontwerp REINFORCED, verbetering PROVEN

Every proof is tagged `[demo-seed]` in its concept_summary for easy cleanup.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from evaluations.models import Evaluation, Finding
from skills.models import LearningProof, Skill


DEMO_MARKER = "[demo-seed]"


# (student_email, skill_slug, status, days_since_taught, proof_evidence_count)
ARCHETYPES = [
    # Kai — struggler, mixed pattern
    ("kai.nguyen@student.mediacollege.nl", "veiligheid",     "relapsed",    21, 1),
    ("kai.nguyen@student.mediacollege.nl", "testen",         "pending",     14, 1),
    ("kai.nguyen@student.mediacollege.nl", "verbetering",    "taught",       7, 0),
    ("kai.nguyen@student.mediacollege.nl", "code_kwaliteit", "pending",     10, 1),
    # Sanne — weak on tests
    ("sanne.bakker@student.mediacollege.nl", "testen",       "relapsed",    18, 2),
    ("sanne.bakker@student.mediacollege.nl", "samenwerking", "proven",      25, 3),
    # Lucas — solid security
    ("lucas.vandijk@student.mediacollege.nl", "veiligheid",  "proven",      30, 4),
    ("lucas.vandijk@student.mediacollege.nl", "testen",      "proven",      22, 3),
    # Jan — reinforced on quality
    ("jan.deboer@student.mediacollege.nl", "code_kwaliteit", "reinforced",  45, 6),
    ("jan.deboer@student.mediacollege.nl", "samenwerking",   "proven",      28, 3),
    # Fatima — strongest, reinforced design + verbetering
    ("fatima.elamrani@student.mediacollege.nl", "code_ontwerp", "reinforced", 50, 7),
    ("fatima.elamrani@student.mediacollege.nl", "verbetering",  "proven",     32, 4),
]


CONCEPT_COPY = {
    "veiligheid": (
        f"{DEMO_MARKER} Input-validatie en veilige query-patronen — "
        "gebruik parameterized queries, valideer gebruikers-input, geen hardcoded secrets."
    ),
    "testen": (
        f"{DEMO_MARKER} Edge cases zijn geen extra — ze zijn de test. "
        "Happy path alleen toont niet dat je code werkt onder druk."
    ),
    "verbetering": (
        f"{DEMO_MARKER} Refactor proactief — TODO is geen einddoel, "
        "maar een uitnodiging om dit beter te maken voordat iemand anders het ziet."
    ),
    "code_kwaliteit": (
        f"{DEMO_MARKER} Duidelijke namen, expliciete foutafhandeling, "
        "geen swallow-catch. Code die je morgen nog zelf snapt."
    ),
    "samenwerking": (
        f"{DEMO_MARKER} Commit-messages en PR-beschrijvingen zijn documentatie — "
        "een reviewer moet uit de tekst begrijpen wat je wilde bereiken."
    ),
    "code_ontwerp": (
        f"{DEMO_MARKER} Eén verantwoordelijkheid per functie/module. "
        "Als je moeite hebt de naam te kiezen, doet hij waarschijnlijk te veel."
    ),
}


class Command(BaseCommand):
    help = (
        "Seed placeholder LearningProof rows for the Webdev Q2 2026 dogfood "
        "cohort so the per-criterion dots render during the pitch. "
        "Idempotent; use --wipe to reset."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all [demo-seed] proofs before reseeding.",
        )

    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        from projects.models import Project
        from users.models import Organization

        User = get_user_model()
        dry = opts["dry_run"]
        wipe = opts["wipe"]

        now = timezone.now()

        if wipe and not dry:
            deleted, _ = LearningProof.objects.filter(
                concept_summary__startswith=DEMO_MARKER
            ).delete()
            self.stdout.write(
                self.style.WARNING(f"[wipe] Deleted {deleted} existing demo proofs.")
            )
            # Also wipe the synthetic demo Findings + Evaluations we created.
            Finding.objects.filter(description__startswith=DEMO_MARKER).delete()
            Evaluation.objects.filter(commit_sha__startswith="demoseed-").delete()

        created = 0
        skipped_existing = 0
        skipped_no_user = 0
        skipped_no_skill = 0

        with transaction.atomic():
            for email, slug, status, days_ago, evidence_count in ARCHETYPES:
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    skipped_no_user += 1
                    self.stdout.write(f"  [skip] no user: {email}")
                    continue

                try:
                    skill = Skill.objects.get(slug=slug)
                except Skill.DoesNotExist:
                    skipped_no_skill += 1
                    self.stdout.write(f"  [skip] no skill: {slug}")
                    continue

                # Stable issue_type so re-runs hit the dedup check below.
                issue_type = f"{slug}:demo"

                if LearningProof.objects.filter(
                    user=user, skill=skill, issue_type=issue_type
                ).exists():
                    skipped_existing += 1
                    continue

                if dry:
                    self.stdout.write(
                        f"  [dry] would create proof: user={email} skill={slug} "
                        f"status={status} taught_days_ago={days_ago}"
                    )
                    continue

                # Anchor to a synthetic Finding on a synthetic Evaluation — the
                # LearningProof model requires a non-null finding FK.
                project = (
                    Project.objects.filter(
                        created_by=user
                    ).first()
                    or Project.objects.filter(name__icontains=email.split('@')[0].split('.')[-1]).first()
                    or Project.objects.first()
                )
                if not project:
                    raise CommandError(
                        "No Project rows exist at all — cannot anchor demo proofs."
                    )

                taught_at = now - timedelta(days=days_ago)

                evaluation = Evaluation.objects.create(
                    project=project,
                    commit_sha=f"demoseed-{user.id}-{slug}-{int(taught_at.timestamp())}",
                    branch="main",
                    author_name=user.get_full_name() or email.split("@")[0],
                    author=user,
                    created_at=taught_at,
                )
                # auto_now_add overrides created_at on insert; patch via update.
                Evaluation.objects.filter(pk=evaluation.pk).update(created_at=taught_at)

                finding = Finding.objects.create(
                    evaluation=evaluation,
                    title=f"[demo-seed] {skill.name} finding",
                    description=CONCEPT_COPY.get(slug, f"{DEMO_MARKER} {skill.name}"),
                    severity="warning",
                    file_path="demo/synthetic.py",
                    line_start=1,
                    line_end=3,
                    original_code="# demo placeholder",
                )
                finding.skills.add(skill)

                proof = LearningProof.objects.create(
                    user=user,
                    skill=skill,
                    finding=finding,
                    issue_type=issue_type,
                    taught_at=taught_at,
                    understanding_level="got_it",
                    concept_summary=CONCEPT_COPY.get(slug, f"{DEMO_MARKER} {skill.name}"),
                    status=LearningProof.Status.PENDING,  # initial; mark_* transitions below
                    proof_evidence_count=evidence_count,
                )

                commit_sha = f"demoseed-{user.id}-{slug}"
                if status == "proven":
                    proof.mark_proven(commit_sha)
                elif status == "reinforced":
                    proof.mark_proven(commit_sha)
                    proof.mark_reinforced(commit_sha + "-r")
                elif status == "relapsed":
                    # Transition through proven → relapsed to model the "they got
                    # it once, then regressed" pathway; penalty is heavier.
                    proof.mark_proven(commit_sha)
                    proof.mark_relapsed(commit_sha + "-r")
                elif status == "pending":
                    proof.status = LearningProof.Status.PENDING
                    proof.save(update_fields=["status", "updated_at"])
                elif status == "taught":
                    proof.status = LearningProof.Status.TAUGHT
                    proof.save(update_fields=["status", "updated_at"])
                else:
                    raise CommandError(f"unknown archetype status: {status}")

                created += 1

            if dry:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("DRY-RUN — no writes."))
                return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo LearningProofs — ready"))
        self.stdout.write(f"  created        : {created}")
        self.stdout.write(f"  already existed: {skipped_existing}")
        self.stdout.write(f"  no user match  : {skipped_no_user}")
        self.stdout.write(f"  no skill match : {skipped_no_skill}")
        total_demo = LearningProof.objects.filter(
            concept_summary__startswith=DEMO_MARKER
        ).count()
        self.stdout.write(f"  total demo proofs in DB: {total_demo}")
