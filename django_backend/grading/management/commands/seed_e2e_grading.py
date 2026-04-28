"""
seed_e2e_grading — idempotent local seed for Nakijken Copilot v1 (Leera) E2E
testing.

Creates the minimum grading scaffolding (Cohort + Rubric + Course +
CohortMembership) linking a student to a GitHub repo inside an existing
organization. Designed to "just work" against yanic's local DB:

    python manage.py seed_e2e_grading

Defaults target the itec org with yanick007.dev@gmail.com (teacher) and
tester@reviewhub.com (student) pointing at github.com/inno8/codelens-test.

Running twice is safe — the command uses get_or_create and explicit
validation to avoid partial writes. Use --dry-run to preview.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grading.models import Cohort, CohortMembership, Course, Rubric
from grading.rubric_defaults import CREBO_RUBRIC_CRITERIA


DEFAULT_ORG_SLUG = "itec"
DEFAULT_TEACHER_EMAIL = "yanick007.dev@gmail.com"
DEFAULT_STUDENT_EMAIL = "tester@reviewhub.com"
DEFAULT_REPO_URL = "https://github.com/inno8/codelens-test"
DEFAULT_COHORT_NAME = "E2E Dogfood"
DEFAULT_COURSE_NAME = "E2E Test Course"
DEFAULT_RUBRIC_NAME = "MBO-4 Software Developer Rubric (Crebo 25604)"


# Backwards-compat alias: seed_dogfood_cohort imports RUBRIC_CRITERIA from here.
RUBRIC_CRITERIA = CREBO_RUBRIC_CRITERIA


class Command(BaseCommand):
    help = (
        "Seed an idempotent local E2E grading scaffolding (Cohort, Rubric, "
        "Course, CohortMembership) for Nakijken Copilot v1 dogfooding."
    )

    def add_arguments(self, parser):
        parser.add_argument("--org-slug", default=DEFAULT_ORG_SLUG)
        parser.add_argument("--teacher-email", default=DEFAULT_TEACHER_EMAIL)
        parser.add_argument("--student-email", default=DEFAULT_STUDENT_EMAIL)
        parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
        parser.add_argument("--cohort-name", default=DEFAULT_COHORT_NAME)
        parser.add_argument("--course-name", default=DEFAULT_COURSE_NAME)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the plan without touching the DB.",
        )

    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        from users.models import Organization

        User = get_user_model()

        org_slug = opts["org_slug"]
        teacher_email = opts["teacher_email"]
        student_email = opts["student_email"]
        repo_url = opts["repo_url"]
        cohort_name = opts["cohort_name"]
        course_name = opts["course_name"]
        dry_run = opts["dry_run"]

        # ── Lookup (fail loud before any write) ──
        try:
            org = Organization.objects.get(slug=org_slug)
        except Organization.DoesNotExist:
            raise CommandError(
                f"Organization with slug={org_slug!r} not found. "
                f"Refusing to auto-create orgs."
            )

        try:
            teacher = User.objects.get(email=teacher_email)
        except User.DoesNotExist:
            raise CommandError(f"Teacher user with email={teacher_email!r} not found.")

        try:
            student = User.objects.get(email=student_email)
        except User.DoesNotExist:
            raise CommandError(f"Student user with email={student_email!r} not found.")

        # ── Pre-flight: student in different cohort? ──
        existing_membership = CohortMembership.objects.filter(student=student).first()
        if existing_membership and existing_membership.cohort.name != cohort_name:
            raise CommandError(
                f"Student {student_email!r} already has a CohortMembership in "
                f"cohort {existing_membership.cohort.name!r} (id="
                f"{existing_membership.cohort_id}). A student may only belong "
                f"to one cohort. Remove the existing membership first — refusing "
                f"to silently migrate."
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN — no DB writes."))
            self.stdout.write(f"Would use Organization: {org.name} (id={org.id}, slug={org.slug})")
            self.stdout.write(f"Would get-or-create Cohort:  {cohort_name!r} in org {org.slug!r}")
            self.stdout.write(
                f"Would get-or-create Rubric:  {DEFAULT_RUBRIC_NAME!r} "
                f"({len(RUBRIC_CRITERIA)} criteria) owner={teacher.email}"
            )
            self.stdout.write(
                f"Would get-or-create Course:  {course_name!r} in cohort "
                f"{cohort_name!r}, owner={teacher.email}"
            )
            self.stdout.write(
                f"Would get-or-create CohortMembership: {student.email} -> {repo_url}"
            )
            return

        # ── Writes (atomic for all-or-nothing semantics) ──
        with transaction.atomic():
            cohort, cohort_created = Cohort.objects.get_or_create(
                org=org,
                name=cohort_name,
            )

            rubric, rubric_created = Rubric.objects.get_or_create(
                org=org,
                name=DEFAULT_RUBRIC_NAME,
                defaults={
                    "owner": teacher,
                    "criteria": RUBRIC_CRITERIA,
                    "calibration": {},
                },
            )

            course, course_created = Course.objects.get_or_create(
                cohort=cohort,
                name=course_name,
                defaults={
                    "org": org,
                    "owner": teacher,
                    "rubric": rubric,
                    "source_control_type": Course.SourceControlType.GITHUB_ORG,
                },
            )

            # CohortMembership: OneToOne on student.
            membership, membership_created = CohortMembership.objects.get_or_create(
                student=student,
                defaults={
                    "cohort": cohort,
                    "student_repo_url": repo_url,
                },
            )

            if not membership_created and membership.student_repo_url != repo_url:
                old_url = membership.student_repo_url
                membership.student_repo_url = repo_url
                membership.save(update_fields=["student_repo_url"])
                self.stdout.write(self.style.WARNING(
                    f"Updated CohortMembership repo_url: {old_url!r} -> {repo_url!r}"
                ))

        # ── Summary ──
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Leera E2E grading scaffolding — ready"))
        self.stdout.write("")
        self.stdout.write(f"Org:         {org.slug} (id={org.id})")
        self.stdout.write(
            f"Cohort:      {cohort.name!r} (id={cohort.id})"
            + ("  [new]" if cohort_created else "  [existing]")
        )
        self.stdout.write(
            f"Course:      {course.name!r} (id={course.id})"
            + ("  [new]" if course_created else "  [existing]")
        )
        self.stdout.write(
            f"Rubric:      {rubric.name!r} (id={rubric.id}, "
            f"{len(rubric.criteria)} criteria)"
            + ("  [new]" if rubric_created else "  [existing]")
        )
        self.stdout.write(f"Teacher:     {teacher.email} (id={teacher.id})")
        self.stdout.write(
            f"Student:     {student.email} (id={student.id}) -> {repo_url}"
        )
        self.stdout.write("")
        self.stdout.write("Webhook URL: http://localhost:8000/api/grading/webhooks/github/")
        self.stdout.write(
            f"Inbox URL:   http://localhost:5173/grading (log in as {teacher.email})"
        )
        self.stdout.write(
            f"Student PR:  push to {repo_url} -> creates GradingSession"
        )
        self.stdout.write("")
        self.stdout.write(
            "Next: trigger the tester agent (tester-manual-run) to push code "
            "to codelens-test."
        )
