"""
`python manage.py backfill_student_history
    --repo=<owner/name> --user=<user_id> --cohort=<cohort_id>
    [--days=90] [--dry-run]`

Seeds a student's profile with real historical PRs from a GitHub repo so
the May 7 Media College Portfolio Day demo can show a convincing multi-
month growth arc.

Design: Workstream H (compressed) of Nakijken Copilot v1 — Leera v0.9.

Why: fresh dogfood starting Apr 27 only gives 10 days of data by pitch
day. Founder runs this once against his own Laravel (or any) repo with
60-90 days of merged PRs and the Bayesian skill model accumulates
observations spanning real historical dates, so the growth chart plots
over time.

Key guarantees:
  1. NO LLM calls. Layer 1 only (regex-based deterministic analyzer).
     Rationale: 60 PRs * 3 students * €0.03 = €5.40 per backfill run, not
     worth it for seed data. Real LLM grading happens on future live PRs.
  2. Historical timestamps preserved. Every created row
     (Submission, GradingSession.posted_at, SkillObservation.created_at,
     DeterministicFinding.created_at) is stamped with the PR's real
     close/merge date, NOT now(). Django auto_now_add is overridden via
     a QuerySet.update() pass immediately after creation.
  3. Idempotent. Re-running skips PRs whose pr_url already has a
     Submission.
  4. Flexible user attribution. --user=N attaches all Submissions to the
     given User regardless of the GitHub PR author, because this seeds
     one student's profile with the founder's commit history.

Example:
  export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx
  python manage.py backfill_student_history \\
      --repo=assignon/laravel-portfolio \\
      --user=42 --cohort=7 --days=90
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone as dt_tz
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grading.models import (
    Cohort,
    Course,
    GradingSession,
    Rubric,
    SessionEvaluation,
    Submission,
    SubmissionContributor,
)
from grading.services.github_backfill import (
    BackfillError,
    PRAnalysis,
    analyze_pr,
    fetch_pr_files,
    get_token,
    iter_merged_prs,
)

log = logging.getLogger(__name__)
User = get_user_model()


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class Command(BaseCommand):
    help = (
        "Backfill historical merged PRs from a GitHub repo into Submissions, "
        "GradingSessions, DeterministicFindings, and SkillObservations with "
        "real historical timestamps. No LLM calls — Layer 1 only."
    )

    def add_arguments(self, parser):
        parser.add_argument("--repo", required=True, help="GitHub owner/name, e.g. foo/bar")
        parser.add_argument("--user", required=True, type=int,
                            help="User id to attribute PRs to (the student seed target).")
        parser.add_argument("--cohort", required=True, type=int,
                            help="Cohort id — picks the course to attach submissions to.")
        parser.add_argument("--days", type=int, default=90,
                            help="Backfill window in days (default 90).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print what would happen, write nothing.")

    # ── entry point ────────────────────────────────────────────────
    def handle(self, *args, **opts):
        repo = opts["repo"]
        if "/" not in repo:
            raise CommandError("--repo must be in 'owner/name' form")
        user_id = opts["user"]
        cohort_id = opts["cohort"]
        days = opts["days"]
        dry_run = opts["dry_run"]

        try:
            token = get_token()
        except BackfillError as e:
            raise CommandError(str(e))

        try:
            student = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise CommandError(f"User id={user_id} not found")

        try:
            cohort = Cohort.objects.get(pk=cohort_id)
        except Cohort.DoesNotExist:
            raise CommandError(f"Cohort id={cohort_id} not found")

        course = cohort.courses.order_by("created_at").first()
        if not course:
            raise CommandError(
                f"Cohort {cohort_id} has no courses yet — create at least one before backfill."
            )

        cutoff = datetime.now(dt_tz.utc) - timedelta(days=days)
        self.stdout.write(
            f"Backfilling {repo} into user={student.email} cohort={cohort.name} "
            f"(cutoff {cutoff.date()}, dry_run={dry_run})"
        )

        summary = {"processed": 0, "skipped": 0, "errors": 0, "obs_created": 0,
                   "findings_created": 0}

        try:
            for pr in iter_merged_prs(repo, token=token, cutoff=cutoff):
                try:
                    result = self._process_pr(
                        pr=pr, repo=repo, token=token, student=student,
                        cohort=cohort, course=course, dry_run=dry_run,
                    )
                except BackfillError as e:
                    self.stderr.write(f"PR #{pr.get('number')} failed: {e}")
                    summary["errors"] += 1
                    continue
                except Exception as e:  # defensive; don't let one bad PR stop the run
                    self.stderr.write(f"PR #{pr.get('number')} unexpected error: {e}")
                    summary["errors"] += 1
                    log.exception("backfill_student_history PR processing failed")
                    continue

                if result.get("skipped"):
                    summary["skipped"] += 1
                else:
                    summary["processed"] += 1
                    summary["obs_created"] += result.get("obs_created", 0)
                    summary["findings_created"] += result.get("findings_created", 0)
                self.stdout.write(result["line"])
        except BackfillError as e:
            raise CommandError(str(e))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. processed={summary['processed']} skipped={summary['skipped']} "
            f"errors={summary['errors']} observations={summary['obs_created']} "
            f"findings={summary['findings_created']}"
        ))

    # ── per-PR orchestration ────────────────────────────────────────
    def _process_pr(
        self, *, pr: dict, repo: str, token: str,
        student, cohort: Cohort, course: Course, dry_run: bool,
    ) -> dict:
        number = pr.get("number")
        title = pr.get("title") or ""
        pr_url = pr.get("html_url") or f"https://github.com/{repo}/pull/{number}"
        merged_at = _parse_iso(pr.get("merged_at")) or _parse_iso(pr.get("closed_at"))
        if merged_at is None:
            merged_at = datetime.now(dt_tz.utc)

        # Idempotency: skip if a Submission for this pr_url already exists.
        if Submission.objects.filter(pr_url=pr_url).exists():
            return {"skipped": True,
                    "line": f"PR #{number} | {title[:50]} | skipped (exists)"}

        if dry_run:
            files = fetch_pr_files(repo, number, token=token)
            analysis = analyze_pr(pr, files)
            return {
                "skipped": False,
                "obs_created": 0,
                "findings_created": 0,
                "line": (
                    f"PR #{number} | {title[:50]} | would create "
                    f"{len(analysis.findings)} findings "
                    f"(dry-run, merged_at={merged_at.date()})"
                ),
            }

        files = fetch_pr_files(repo, number, token=token)
        analysis = analyze_pr(pr, files)

        with transaction.atomic():
            submission = self._create_submission(
                pr=pr, pr_url=pr_url, title=title, repo=repo,
                student=student, course=course, merged_at=merged_at,
            )
            # Flexible attribution: primary contributor = the --user target.
            SubmissionContributor.objects.create(
                submission=submission, user=student,
                is_primary_author=True, contribution_fraction=1.0,
                lines_changed=analysis.lines_added + analysis.lines_removed,
                commits_count=int(pr.get("commits") or 0),
            )
            rubric = self._pick_rubric(course)
            session = GradingSession.objects.create(
                org=course.org, submission=submission, rubric=rubric,
                state=GradingSession.State.POSTED,
                posted_at=merged_at,
                ai_draft_model="backfill-layer1",
                ai_draft_generated_at=merged_at,
            )
            # Stamp posted_at / created_at to the historical date.
            GradingSession.objects.filter(pk=session.pk).update(
                posted_at=merged_at, created_at=merged_at, updated_at=merged_at,
            )
            # Also push Submission.created_at back to the merge date so the
            # growth arc plots over real time.
            Submission.objects.filter(pk=submission.pk).update(
                created_at=merged_at, updated_at=merged_at,
                status=Submission.Status.GRADED,
            )

            evaluation = self._create_evaluation(
                pr=pr, repo=repo, student=student, analysis=analysis,
                merged_at=merged_at,
            )
            SessionEvaluation.objects.create(
                grading_session=session, evaluation=evaluation,
            )

            findings_created = self._persist_findings(evaluation, analysis, merged_at)
            obs_created = self._persist_skill_observations(
                student=student, evaluation=evaluation, analysis=analysis,
                merged_at=merged_at,
            )

        return {
            "skipped": False,
            "obs_created": obs_created,
            "findings_created": findings_created,
            "line": (
                f"PR #{number} | {title[:50]} | "
                f"{findings_created} findings | {obs_created} skills updated "
                f"(merged_at={merged_at.date()})"
            ),
        }

    # ── helpers ─────────────────────────────────────────────────────
    def _create_submission(self, *, pr, pr_url, title, repo, student, course, merged_at):
        return Submission.objects.create(
            org=course.org, course=course, student=student,
            repo_full_name=repo, pr_number=pr.get("number") or 0,
            pr_url=pr_url, pr_title=title[:500],
            base_branch=(pr.get("base") or {}).get("ref") or "main",
            head_branch=(pr.get("head") or {}).get("ref") or "unknown",
            status=Submission.Status.GRADED,
        )

    def _pick_rubric(self, course: Course) -> Rubric:
        if course.rubric_id:
            return course.rubric
        # Fall back to any org rubric, or create a minimal placeholder so
        # the FK is satisfiable. Templates may also be used.
        rubric = Rubric.objects.filter(org=course.org).first()
        if rubric:
            return rubric
        rubric = Rubric.objects.filter(is_template=True).first()
        if rubric:
            return rubric
        return Rubric.objects.create(
            org=course.org, name="Backfill default",
            criteria=[{"id": "default", "name": "Default",
                       "weight": 1.0,
                       "levels": [{"score": 1}, {"score": 4}]}],
        )

    def _get_or_create_project(self, repo: str, student):
        from projects.models import Project
        owner, _, name = repo.partition("/")
        project, _ = Project.objects.get_or_create(
            provider=Project.Provider.GITHUB,
            repo_owner=owner, repo_name=name,
            defaults={"name": name, "created_by": student},
        )
        return project

    def _create_evaluation(self, *, pr, repo, student, analysis: PRAnalysis, merged_at):
        from evaluations.models import Evaluation
        project = self._get_or_create_project(repo, student)
        head_sha = (pr.get("head") or {}).get("sha") or f"pr-{pr.get('number')}"
        evaluation = Evaluation.objects.create(
            project=project, author=student,
            commit_sha=head_sha[:40],
            commit_message=(pr.get("title") or "")[:500],
            commit_timestamp=merged_at,
            branch=(pr.get("head") or {}).get("ref") or "unknown",
            author_name=student.username or student.email,
            author_email=student.email or "",
            files_changed=len(analysis.files),
            lines_added=analysis.lines_added,
            lines_removed=analysis.lines_removed,
            overall_score=analysis.quality_score,
            status="completed",
            llm_model="",   # backfill never calls LLM
            evaluated_at=merged_at,
        )
        # Override auto_now_add to preserve historical date.
        Evaluation.objects.filter(pk=evaluation.pk).update(
            created_at=merged_at, evaluated_at=merged_at,
        )
        evaluation.created_at = merged_at
        return evaluation

    def _persist_findings(self, evaluation, analysis: PRAnalysis, merged_at):
        from evaluations.models import DeterministicFinding
        rows = [
            DeterministicFinding(evaluation=evaluation, **f.as_kwargs())
            for f in analysis.findings
        ]
        if not rows:
            return 0
        created = DeterministicFinding.objects.bulk_create(rows)
        DeterministicFinding.objects.filter(
            pk__in=[r.pk for r in created]
        ).update(created_at=merged_at)
        return len(created)

    def _persist_skill_observations(self, *, student, evaluation, analysis: PRAnalysis, merged_at):
        """
        Aggregate findings by skill_slug and write one SkillObservation per
        skill (or a single 'clean_code' observation if there were zero
        findings — a clean PR is still signal).
        """
        from skills.models import Skill, SkillMetric, SkillObservation

        by_skill: dict[str, dict] = {}
        for f in analysis.findings:
            slug = f.skill_slug or "clean_code"
            bucket = by_skill.setdefault(slug, {
                "critical": 0, "warning": 0, "info": 0, "suggestion": 0, "total": 0,
            })
            sev = f.severity if f.severity in bucket else "warning"
            bucket[sev] += 1
            bucket["total"] += 1

        # Clean-PR signal: always emit an observation against 'clean_code'
        # so a streak of spotless PRs still raises the bayesian score.
        if "clean_code" not in by_skill:
            by_skill["clean_code"] = {
                "critical": 0, "warning": 0, "info": 0, "suggestion": 0, "total": 0,
            }

        quality = analysis.quality_score
        weight = analysis.complexity_weight
        lines = analysis.lines_added + analysis.lines_removed

        created_count = 0
        for slug, counts in by_skill.items():
            skill = Skill.objects.filter(slug=slug).first()
            if skill is None:
                # Fresh DB / no seed data — skip this observation gracefully.
                # The demo seed script populates Skills separately.
                continue
            obs = SkillObservation.objects.create(
                user=student,
                project=evaluation.project,
                evaluation=evaluation,
                skill=skill,
                commit_sha=evaluation.commit_sha,
                quality_score=quality,
                complexity_weight=weight,
                weighted_score=round(quality * weight, 2),
                lines_changed=lines,
                issue_count=counts["total"],
                critical_count=counts["critical"],
                warning_count=counts["warning"],
                info_count=counts["info"],
                suggestion_count=counts["suggestion"],
            )
            SkillObservation.objects.filter(pk=obs.pk).update(created_at=merged_at)
            created_count += 1

            metric, _ = SkillMetric.objects.get_or_create(
                user=student, project=evaluation.project, skill=skill,
            )
            metric.update_bayesian(
                weighted_score=obs.weighted_score,
                complexity_weight=weight,
            )

        return created_count
