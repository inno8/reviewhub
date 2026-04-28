"""
seed_dogfood_cohort — idempotent dogfood seeder for the Leera
(Nakijken Copilot v1) demo / pitch / product-video capture.

Creates a realistic Dutch MBO-4 webdev cohort ("Webdev Q2 2026") with
5 students, 20 Submissions (PRs) spread across the last 3 weeks, and
20 GradingSessions covering every state in the machine so every UI
screen has something to render:

    4 × PENDING, 2 × DRAFTING, 8 × DRAFTED, 2 × REVIEWING,
    3 × POSTED, 1 × PARTIAL

DRAFTED / REVIEWING / POSTED sessions carry rich Dutch teacher-voice
ai_draft_comments (with original_snippet, suggested_snippet,
teacher_explanation) plus ai_draft_scores so the Student Snapshot
radar + Recurring Errors views come alive.

Usage:

    python manage.py seed_dogfood_cohort --dry-run
    python manage.py seed_dogfood_cohort
    python manage.py seed_dogfood_cohort --wipe      # nukes & reseeds

Safe to re-run — every write is get_or_create with stable keys. PR
numbers are derived deterministically from a hash of (student_email,
pr_title) so re-runs match existing Submission rows.

Defaults target yanic's local DB: itec org, yanick007.dev@gmail.com
teacher.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from grading.models import (
    Cohort,
    CohortMembership,
    CohortTeacher,
    Course,
    GradingSession,
    Rubric,
    Submission,
)

from grading.rubric_defaults import CREBO_RUBRIC_CRITERIA as RUBRIC_CRITERIA


DEFAULT_ORG_SLUG = "itec"
DEFAULT_TEACHER_EMAIL = "yanick007.dev@gmail.com"
DEFAULT_COHORT_NAME = "Webdev Q2 2026"
DEFAULT_COURSE_NAME = "Fullstack Web Development"
DEFAULT_RUBRIC_NAME = "MBO-4 Webdev Q2 Rubric (Crebo 25604)"
STUDENT_REPO_ORG = "mediacollege-webdev-q2"


# ── Student roster ──────────────────────────────────────────────────
# (full_name, email_local, slug, archetype) — archetype drives score profile
STUDENTS = [
    ("Jan de Boer",      "jan.deboer",      "jan-deboer",      "strong"),
    ("Fatima el Amrani", "fatima.elamrani", "fatima-elamrani", "solid"),
    ("Lucas van Dijk",   "lucas.vandijk",   "lucas-vandijk",   "mid"),
    ("Sanne Bakker",     "sanne.bakker",    "sanne-bakker",    "weak_testing"),
    ("Kai Nguyen",       "kai.nguyen",      "kai-nguyen",      "struggling"),
]


# ── PR catalogue (20 PRs, a realistic webdev curriculum arc) ────────
# (pr_title, file_path, head_branch_slug)
PR_CATALOGUE = [
    ("Add contact form validation",              "src/forms/contact.js",          "feat/contact-validation"),
    ("Implement user login with bcrypt",         "src/auth/login.js",             "feat/login-bcrypt"),
    ("Build REST API for blog posts",            "src/api/posts.js",              "feat/blog-api"),
    ("Refactor cart state to Pinia store",       "src/stores/cart.js",            "refactor/cart-pinia"),
    ("Add input sanitization to comment form",   "src/forms/comment.js",          "fix/comment-sanitize"),
    ("Fix SQL injection in search endpoint",     "src/api/search.js",             "fix/sql-injection"),
    ("Write unit tests for auth middleware",     "src/middleware/auth.test.js",   "test/auth-middleware"),
    ("Add error boundaries to checkout flow",    "src/views/Checkout.vue",        "feat/error-boundaries"),
    ("Style product card with Tailwind",         "src/components/ProductCard.vue","feat/product-card-style"),
    ("Add ARIA labels to navigation",            "src/components/NavBar.vue",     "a11y/nav-aria"),
    ("Hash passwords before DB insert",          "src/services/users.js",         "fix/password-hash"),
    ("Add pagination to blog index",             "src/views/BlogIndex.vue",       "feat/blog-pagination"),
    ("Validate email format on signup",          "src/forms/signup.js",           "feat/signup-email-validate"),
    ("Fix XSS in user-profile bio render",       "src/views/Profile.vue",         "fix/profile-xss"),
    ("Add loading skeleton to product list",     "src/components/ProductList.vue","feat/list-skeleton"),
    ("Write integration tests for cart flow",    "tests/cart.spec.js",            "test/cart-integration"),
    ("Normalize user input with Zod schema",     "src/validation/user.js",        "feat/zod-user"),
    ("Protect admin route with role guard",      "src/router/guards.js",          "feat/admin-guard"),
    ("Cache API responses with TTL",             "src/services/cache.js",         "feat/api-cache"),
    ("Add dark-mode toggle with Tailwind",       "src/components/ThemeToggle.vue","feat/dark-mode"),
]


# ── Comment templates (Dutch teacher-voice) ─────────────────────────
# Each: (body, original_snippet, suggested_snippet, teacher_explanation, default_line)
COMMENT_TEMPLATES = [
    {
        "body": (
            "Deze catch-block vangt de fout maar doet er niets mee. Voor een "
            "gebruiker verdwijnt het probleem dan in het niets — wij willen "
            "loggen én een betekenisvolle fout teruggeven."
        ),
        "original_snippet": "} catch (e) {\n  console.log(e);\n}",
        "suggested_snippet": (
            "} catch (e) {\n"
            "  logger.error('login failed', { userId, err: e });\n"
            "  throw new AuthError('login_failed');\n"
            "}"
        ),
        "teacher_explanation": (
            "In productie wil je deze fout loggen met context (wie, wat, "
            "waar) en hem opnieuw gooien zodat de aanroepende laag kan "
            "beslissen wat er moet gebeuren."
        ),
        "default_line": 42,
    },
    {
        "body": (
            "Je bouwt hier een SQL-query met string-concatenatie. Dat is de "
            "klassieke SQL-injectie — een aanvaller kan nu willekeurige "
            "queries uitvoeren."
        ),
        "original_snippet": (
            "const q = `SELECT * FROM users WHERE email='${email}'`;\n"
            "db.query(q);"
        ),
        "suggested_snippet": (
            "db.query(\n"
            "  'SELECT * FROM users WHERE email = ?',\n"
            "  [email]\n"
            ");"
        ),
        "teacher_explanation": (
            "Gebruik altijd parameterized queries. De database escapet de "
            "waarde dan zelf; jij hoeft er niet meer over na te denken."
        ),
        "default_line": 58,
    },
    {
        "body": (
            "Hier valideer je de input niet voordat je hem opslaat. Een lege "
            "of veel te lange string komt gewoon de database in."
        ),
        "original_snippet": (
            "const { name, email } = req.body;\n"
            "await User.create({ name, email });"
        ),
        "suggested_snippet": (
            "const schema = z.object({\n"
            "  name: z.string().min(1).max(100),\n"
            "  email: z.string().email(),\n"
            "});\n"
            "const data = schema.parse(req.body);\n"
            "await User.create(data);"
        ),
        "teacher_explanation": (
            "Validatie aan de rand van je systeem (de controller) voorkomt "
            "dat vuile data dieper je applicatie in lekt. Zod of Joi doen "
            "dit declaratief en testbaar."
        ),
        "default_line": 23,
    },
    {
        "body": (
            "bcrypt met cost factor 4 is veel te zwak voor productie. Dat "
            "kraakt een moderne GPU in minuten."
        ),
        "original_snippet": "const hash = await bcrypt.hash(pwd, 4);",
        "suggested_snippet": "const hash = await bcrypt.hash(pwd, 12);",
        "teacher_explanation": (
            "Kies een cost factor waarbij één hash ~100ms duurt op je "
            "productie-hardware. Voor 2026 is dat meestal 12. Te laag = "
            "onveilig, te hoog = login-latency."
        ),
        "default_line": 17,
    },
    {
        "body": (
            "Console.log blijft hier in de productiecode staan. Dat lekt "
            "implementatiedetails en vervuilt de server-logs."
        ),
        "original_snippet": "console.log('user payload:', req.body);",
        "suggested_snippet": (
            "logger.debug('user payload received', {\n"
            "  userId: req.user?.id,\n"
            "});"
        ),
        "teacher_explanation": (
            "Gebruik een structured logger (pino, winston) met log-levels. "
            "Dan kun je in dev alles zien en in prod alleen warn+error."
        ),
        "default_line": 34,
    },
    {
        "body": (
            "Je rendert hier user-input direct in de DOM zonder escape. Dat "
            "is een XSS-gat — een kwaadaardige bio kan script draaien bij "
            "iedereen die het profiel bekijkt."
        ),
        "original_snippet": '<div v-html="profile.bio"></div>',
        "suggested_snippet": (
            "<div>{{ profile.bio }}</div>\n"
            "<!-- óf, als je écht HTML wilt toestaan, sanitize met DOMPurify: -->\n"
            '<div v-html="sanitize(profile.bio)"></div>'
        ),
        "teacher_explanation": (
            "v-html omzeilt Vue's auto-escape. Gebruik alleen als je de "
            "bron 100% vertrouwt, of sanitize eerst met DOMPurify."
        ),
        "default_line": 71,
    },
    {
        "body": (
            "Er is geen null-check voordat je .map() aanroept. Als de API "
            "een foutstatus teruggeeft crasht je component."
        ),
        "original_snippet": "const items = data.products.map(p => p.name);",
        "suggested_snippet": (
            "const items = (data.products ?? []).map(p => p.name);"
        ),
        "teacher_explanation": (
            "Defensief programmeren: ga ervan uit dat elke externe bron "
            "kan falen of leeg kan zijn. Een ?? [] of optional chaining "
            "kost niets en voorkomt runtime-crashes."
        ),
        "default_line": 19,
    },
    {
        "body": (
            "Geen enkele test dekt deze nieuwe functie. Voor auth-logica is "
            "dat extra pijnlijk — een regressie hier is meteen een "
            "security-incident."
        ),
        "original_snippet": "// ... login() function body ...",
        "suggested_snippet": (
            "// tests/auth.test.js\n"
            "test('login fails on wrong password', async () => {\n"
            "  const res = await login({ email, password: 'wrong' });\n"
            "  expect(res.ok).toBe(false);\n"
            "  expect(res.error).toBe('invalid_credentials');\n"
            "});"
        ),
        "teacher_explanation": (
            "Minimaal de happy path én één foutpad dekken. Bij auth is de "
            "foutpadtest belangrijker dan de happy path."
        ),
        "default_line": 12,
    },
]


# ── Score archetypes (vary students so radar looks alive) ───────────
# Tuple order matches CREBO_CRITERION_ORDER below.
CREBO_CRITERION_ORDER = (
    "code_ontwerp", "code_kwaliteit", "veiligheid",
    "testen", "verbetering", "samenwerking",
)
SCORE_ARCHETYPES = {
    # (code_ontwerp, code_kwaliteit, veiligheid, testen, verbetering, samenwerking)
    "strong":         (4, 4, 3, 4, 3, 4),
    "solid":          (3, 3, 3, 3, 3, 3),
    "mid":            (3, 3, 3, 2, 2, 3),
    "weak_testing":   (3, 3, 2, 1, 2, 3),
    "struggling":     (2, 2, 2, 1, 2, 2),
}


EVIDENCE_TEMPLATES = {
    "code_ontwerp": {
        1: "Alles in één functie; geen scheiding van verantwoordelijkheden.",
        2: "Basis-opdeling aanwezig, maar veel herhaling; abstractie ontbreekt.",
        3: "Logische opbouw, bestanden met duidelijke rol, weinig coupling.",
        4: "Doordacht ontwerp: herbruikbaar, uitbreidbaar, minimale coupling.",
    },
    "code_kwaliteit": {
        1: "Moeilijk leesbaar; onduidelijke namen; errors worden geslikt.",
        2: "Werkt, maar inconsistent; cryptische namen; fouten stilletjes gecatched.",
        3: "Leesbaar, idiomatic, errors met context afgehandeld.",
        4: "Zelf-documenterend, robuust, edge cases netjes afgedekt.",
    },
    "veiligheid": {
        1: "SQL-query met string-concatenatie — klassieke injectie.",
        2: "Input deels gecontroleerd, maar bcrypt-cost te laag; secrets in code.",
        3: "Parameterized queries, input-validatie met Zod, geen secrets in code.",
        4: "Threat-modeled: rate limiting, CSRF, least-privilege op DB-user.",
    },
    "testen": {
        1: "Geen tests aanwezig in deze PR.",
        2: "Alleen happy-path tests; foutpaden ontbreken.",
        3: "Happy- én error-paden gedekt; redelijke coverage.",
        4: "Edge cases, regressietests, en property-based tests aanwezig.",
    },
    "verbetering": {
        1: "Eerdere review-opmerkingen zijn genegeerd; TODOs blijven staan.",
        2: "Feedback deels verwerkt, zonder onderliggend patroon te herkennen.",
        3: "Feedback consistent verwerkt; kleine verbeteringen uit eigen initiatief.",
        4: "Refactored proactief; verbeteringen gaan verder dan de opdracht.",
    },
    "samenwerking": {
        1: "Commit-messages onduidelijk; geen PR-beschrijving.",
        2: "Basis-beschrijving aanwezig; reacties op review kort of defensief.",
        3: "Duidelijke commits, PR-beschrijving toont context, constructieve reactie.",
        4: "PR documenteert keuzes en trade-offs; reflecteert zelfstandig.",
    },
}


# ── State plan (20 sessions total) ──────────────────────────────────
STATE_PLAN = (
    [GradingSession.State.PENDING]   * 4 +
    [GradingSession.State.DRAFTING]  * 2 +
    [GradingSession.State.DRAFTED]   * 8 +
    [GradingSession.State.REVIEWING] * 2 +
    [GradingSession.State.POSTED]    * 3 +
    [GradingSession.State.PARTIAL]   * 1
)
assert len(STATE_PLAN) == 20


def _stable_pr_number(student_email: str, pr_title: str) -> int:
    """Deterministic PR number in [1, 9999]."""
    h = hashlib.sha256(f"{student_email}:{pr_title}".encode("utf-8")).hexdigest()
    return (int(h[:8], 16) % 9999) + 1


def _jitter_scores(archetype: str, pr_index: int) -> tuple[int, ...]:
    """Vary base archetype scores by PR topic so radar isn't flat.

    Returns a 6-tuple aligned with CREBO_CRITERION_ORDER:
      (code_ontwerp, code_kwaliteit, veiligheid, testen, verbetering, samenwerking)
    """
    base = SCORE_ARCHETYPES[archetype]
    # cycle small adjustments so different PRs show different weak spots
    bumps = [
        (0,  0,  0,  0,  0,  0),
        (0,  1,  0, -1,  0,  1),
        (-1, 0,  1,  0,  1,  0),
        (0, -1,  0,  1, -1,  0),
        (1,  0, -1,  0,  0, -1),
    ][pr_index % 5]
    out = tuple(max(1, min(4, b + j)) for b, j in zip(base, bumps))
    return out


def _build_comments(pr_file: str, n: int) -> list[dict]:
    """Pick `n` comment templates and stamp them with file/line/uuid."""
    out = []
    for i in range(n):
        tpl = COMMENT_TEMPLATES[i % len(COMMENT_TEMPLATES)]
        out.append({
            "file": pr_file,
            "line": tpl["default_line"] + i * 7,
            "body": tpl["body"],
            "original_snippet": tpl["original_snippet"],
            "suggested_snippet": tpl["suggested_snippet"],
            "teacher_explanation": tpl["teacher_explanation"],
            "client_mutation_id": uuid.uuid4().hex,
        })
    return out


def _build_scores(archetype: str, pr_index: int) -> dict:
    scores = _jitter_scores(archetype, pr_index)
    return {
        crit_id: {
            "score": score,
            "evidence": EVIDENCE_TEMPLATES[crit_id][score],
        }
        for crit_id, score in zip(CREBO_CRITERION_ORDER, scores)
    }


class Command(BaseCommand):
    help = (
        "Seed a rich Dutch MBO-4 webdev cohort ('Webdev Q2 2026') with 5 "
        "students, 20 PRs, and 20 GradingSessions in every state — enough "
        "demo data to light up every Leera UI screen for the May 7 pitch."
    )

    def add_arguments(self, parser):
        parser.add_argument("--org-slug", default=DEFAULT_ORG_SLUG)
        parser.add_argument("--teacher-email", default=DEFAULT_TEACHER_EMAIL)
        parser.add_argument("--cohort-name", default=DEFAULT_COHORT_NAME)
        parser.add_argument("--course-name", default=DEFAULT_COURSE_NAME)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the plan without touching the DB.",
        )
        parser.add_argument(
            "--wipe",
            action="store_true",
            help=(
                "Delete everything this command created (matched by cohort "
                "name) before re-seeding. Cohort, Course, CohortTeacher, "
                "CohortMembership, Submissions + GradingSessions all cascade."
            ),
        )

    # ── entry point ──────────────────────────────────────────────────
    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        from users.models import Organization

        User = get_user_model()

        org_slug       = opts["org_slug"]
        teacher_email  = opts["teacher_email"]
        cohort_name    = opts["cohort_name"]
        course_name    = opts["course_name"]
        dry_run        = opts["dry_run"]
        wipe           = opts["wipe"]

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
            raise CommandError(
                f"Teacher user with email={teacher_email!r} not found."
            )

        # ── Pre-flight: student cross-cohort collisions? ──
        collisions = []
        for (_name, local, _slug, _arch) in STUDENTS:
            email = f"{local}@student.mediacollege.nl"
            try:
                u = User.objects.get(email=email)
            except User.DoesNotExist:
                continue
            mem = CohortMembership.objects.filter(student=u).first()
            if mem and mem.cohort.name != cohort_name:
                collisions.append(
                    f"  {email} already in cohort {mem.cohort.name!r} "
                    f"(id={mem.cohort_id})"
                )
        if collisions and not wipe:
            raise CommandError(
                "Refusing to silently migrate students across cohorts. "
                "Move or remove these memberships first (or rerun with "
                "--wipe to nuke the target cohort):\n" + "\n".join(collisions)
            )

        # ── Dry run: plan-only output ──
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN — no DB writes."))
            self.stdout.write(f"Org:         {org.slug}")
            self.stdout.write(f"Cohort:      {cohort_name!r}")
            self.stdout.write(f"Course:      {course_name!r}")
            self.stdout.write(f"Rubric:      {DEFAULT_RUBRIC_NAME!r}")
            self.stdout.write(f"Teacher:     {teacher.email}")
            self.stdout.write(f"Students:    {len(STUDENTS)}")
            self.stdout.write(f"Submissions: {len(STATE_PLAN)}")
            self.stdout.write("State distribution:")
            from collections import Counter
            for st, n in Counter(STATE_PLAN).items():
                self.stdout.write(f"  {st:<11} -> {n}")
            return

        # ── Wipe (optional) ──
        if wipe:
            self.stdout.write(self.style.WARNING(
                f"--wipe: deleting cohort {cohort_name!r} in org {org.slug!r}"
            ))
            with transaction.atomic():
                Cohort.objects.filter(org=org, name=cohort_name).delete()

        # ── Writes (atomic all-or-nothing for the whole seed) ──
        created_session_ids: list[tuple[int, str]] = []
        skill_obs_count = 0

        with transaction.atomic():
            cohort, cohort_new = Cohort.objects.get_or_create(
                org=org, name=cohort_name,
                defaults={"year": "2026-2027"},
            )

            rubric, rubric_new = Rubric.objects.get_or_create(
                org=org, name=DEFAULT_RUBRIC_NAME,
                defaults={
                    "owner": teacher,
                    "criteria": RUBRIC_CRITERIA,
                    "calibration": {
                        "tone": "informal",
                        "language": "nl",
                        "depth": "detailed",
                    },
                },
            )

            course, course_new = Course.objects.get_or_create(
                cohort=cohort, name=course_name,
                defaults={
                    "org": org,
                    "owner": teacher,
                    "rubric": rubric,
                    "source_control_type": Course.SourceControlType.GITHUB_ORG,
                },
            )

            CohortTeacher.objects.get_or_create(cohort=cohort, teacher=teacher)

            # Students + memberships
            students: list = []
            for (full_name, local, slug, archetype) in STUDENTS:
                email = f"{local}@student.mediacollege.nl"
                first, _, last = full_name.partition(" ")
                user, user_new = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "first_name": first,
                        "last_name": last,
                        "role": User.Role.DEVELOPER,
                        "organization": org,
                    },
                )
                if user_new:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])

                repo_url = f"https://github.com/{STUDENT_REPO_ORG}/{slug}-portfolio"
                mem, mem_new = CohortMembership.objects.get_or_create(
                    student=user,
                    defaults={"cohort": cohort, "student_repo_url": repo_url},
                )
                if not mem_new and mem.cohort_id != cohort.id:
                    raise CommandError(
                        f"Student {email} is in another cohort "
                        f"(id={mem.cohort_id}); refusing to silently migrate."
                    )
                students.append((user, archetype, slug, repo_url))

            # Submissions + GradingSessions
            now = timezone.now()
            for i, state in enumerate(STATE_PLAN):
                student, archetype, slug, repo_url = students[i % len(students)]
                pr_title, pr_file, head_branch = PR_CATALOGUE[i]
                pr_number = _stable_pr_number(student.email, pr_title)
                repo_full_name = f"{STUDENT_REPO_ORG}/{slug}-portfolio"

                sub, sub_new = Submission.objects.get_or_create(
                    course=course,
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    defaults={
                        "org": org,
                        "student": student,
                        "pr_url": f"{repo_url}/pull/{pr_number}",
                        "pr_title": pr_title,
                        "base_branch": "main",
                        "head_branch": head_branch,
                        "status": Submission.Status.SUBMITTED,
                    },
                )

                # Back-date created_at (auto_now_add would clobber it at insert)
                age_days = (i % 21) + 1  # spread across last 3 weeks
                backdated = now - timedelta(days=age_days, hours=i)
                Submission.objects.filter(pk=sub.pk).update(created_at=backdated)

                session, sess_new = GradingSession.objects.get_or_create(
                    submission=sub,
                    defaults={
                        "org": org,
                        "rubric": rubric,
                        "state": state,
                    },
                )

                # Always set state (safe on re-run — same value)
                updates: dict = {"state": state}

                has_draft = state in {
                    GradingSession.State.DRAFTED,
                    GradingSession.State.REVIEWING,
                    GradingSession.State.POSTED,
                    GradingSession.State.PARTIAL,
                }
                if has_draft:
                    scores = _build_scores(archetype, i)
                    n_comments = 3 + (i % 4)  # 3-6 comments
                    comments = _build_comments(pr_file, n_comments)
                    updates.update({
                        "ai_draft_scores": scores,
                        "ai_draft_comments": comments,
                        "ai_draft_model": "claude-3-5-sonnet-20241022",
                        "ai_draft_generated_at": backdated + timedelta(minutes=3),
                    })

                if state == GradingSession.State.DRAFTING:
                    updates.update({
                        "ai_draft_model": "claude-3-5-sonnet-20241022",
                    })

                if state in {GradingSession.State.REVIEWING,
                             GradingSession.State.POSTED,
                             GradingSession.State.PARTIAL}:
                    updates["docent_review_started_at"] = (
                        backdated + timedelta(minutes=30)
                    )

                if state == GradingSession.State.POSTED:
                    updates.update({
                        "final_scores": updates["ai_draft_scores"],
                        "final_comments": updates["ai_draft_comments"],
                        "final_summary": (
                            "Goed bezig — let vooral op error-handling en "
                            "input-validatie bij de volgende PR."
                        ),
                        "sending_started_at": backdated + timedelta(minutes=33),
                        "posted_at": backdated + timedelta(minutes=34),
                        "docent_review_time_seconds": 240,
                    })

                if state == GradingSession.State.PARTIAL:
                    updates.update({
                        "sending_started_at": backdated + timedelta(minutes=33),
                        "partial_post_error": {
                            "error_class": "GithubAPIError",
                            "message": "502 Bad Gateway on comment 3/5",
                            "failed_at_comment_idx": 2,
                        },
                    })

                for k, v in updates.items():
                    setattr(session, k, v)
                session.save()

                # Align session.created_at with the submission
                GradingSession.objects.filter(pk=session.pk).update(
                    created_at=backdated + timedelta(seconds=30)
                )

                created_session_ids.append((session.id, state))

            # ── Link a representative Evaluation per Submission (for skill binding) ──
            from evaluations.models import Evaluation
            from grading.models import SessionEvaluation
            from grading.services.virtual_project import get_or_create_virtual_project

            for i, (sess_id, state) in enumerate(created_session_ids):
                session = GradingSession.objects.get(pk=sess_id)
                sub = session.submission
                project = get_or_create_virtual_project(sub)
                commit_sha = hashlib.sha1(
                    f"{sub.repo_full_name}:{sub.pr_number}".encode()
                ).hexdigest()[:40]

                evaluation, _ = Evaluation.objects.get_or_create(
                    project=project,
                    commit_sha=commit_sha,
                    defaults={
                        "author": sub.student,
                        "author_name": sub.student.get_full_name() or sub.student.email,
                        "author_email": sub.student.email,
                        "commit_message": sub.pr_title,
                        "branch": sub.head_branch,
                        "status": Evaluation.Status.COMPLETED,
                        "files_changed": 3,
                        "lines_added": 45,
                        "lines_removed": 12,
                        "overall_score": 72.0,
                    },
                )
                SessionEvaluation.objects.get_or_create(
                    grading_session=session,
                    evaluation=evaluation,
                    defaults={"included_in_draft": True},
                )

        # ── Skill binding (outside the main atomic so failures here
        #    don't rollback the seed; skill_binding uses its own atomic) ──
        from grading.services.skill_binding import bind_rubric_to_observations

        for sess_id, state in created_session_ids:
            session = GradingSession.objects.get(pk=sess_id)
            if not session.ai_draft_scores:
                continue
            try:
                skill_obs_count += bind_rubric_to_observations(session)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    f"  bind skill obs for session={sess_id} FAILED: {exc}"
                )

        # ── Roll SkillObservations up into SkillMetric (Bayesian) ──
        # The snapshot UI reads SkillMetric, not SkillObservation. Without
        # this step the radar shows "No skill data yet" for every seeded
        # student even though observations exist.
        from skills.models import SkillMetric, SkillObservation

        metric_upserts = 0
        for (student, _arch, _slug, _repo) in students:
            obs_qs = (
                SkillObservation.objects
                .filter(user=student)
                .select_related("skill", "project")
                .order_by("created_at")
            )
            # Reset so re-runs don't double-count: delete existing metrics
            # for this student and rebuild from observations.
            SkillMetric.objects.filter(user=student).delete()
            for obs in obs_qs:
                metric, _ = SkillMetric.objects.get_or_create(
                    user=student, project=obs.project, skill=obs.skill,
                )
                metric.update_bayesian(
                    weighted_score=obs.weighted_score,
                    complexity_weight=obs.complexity_weight,
                )
                metric_upserts += 1

        # ── Pattern seeding (recurring issues by student archetype) ──
        # The snapshot's "Recurring patterns" section reads Pattern rows.
        # Without this the weakest students show "No recurring issues."
        from evaluations.models import Pattern
        from projects.models import Project

        # archetype -> [(pattern_type, pattern_key, frequency)]
        PATTERN_PLAN = {
            "struggling": [
                ("error_handling", "swallow-catch",          4),
                ("security",       "sql-string-concat",      3),
                ("validation",     "no-input-validation",    3),
            ],
            "weak_testing": [
                ("testing",        "no-error-path-tests",    3),
                ("testing",        "happy-path-only",        2),
                # Shared with `struggling` → cohort-wide recurring error
                # visible in the cohort overview (affects ≥2 students).
                ("error_handling", "swallow-catch",          2),
            ],
            "mid": [
                ("code_quality",   "console-log-in-prod",    2),
                # Shared with `struggling` so the cohort overview shows
                # at least 2 distinct cross-student patterns.
                ("validation",     "no-input-validation",    1),
            ],
            "solid": [],
            "strong": [],
        }

        pattern_upserts = 0
        now_ts = timezone.now()
        # Pick any project we created via the skill binding (they share the
        # virtual_project shim). Pattern.project is nullable, but attaching
        # one is harmless and keeps existing queries happy.
        any_project = Project.objects.filter(
            skill_observations__user__in=[s for (s, _, _, _) in students]
        ).first()

        for (student, archetype, _slug, _repo) in students:
            plan = PATTERN_PLAN.get(archetype, [])
            for (ptype, pkey, freq) in plan:
                pat, _created = Pattern.objects.get_or_create(
                    user=student,
                    project=any_project,
                    pattern_key=pkey,
                    defaults={
                        "pattern_type": ptype,
                        "frequency": freq,
                        "is_resolved": False,
                    },
                )
                # Force realistic first_seen / last_seen (auto_now_add /
                # auto_now would clobber these on insert / save). Update via
                # .update() to sidestep auto_now behavior.
                Pattern.objects.filter(pk=pat.pk).update(
                    pattern_type=ptype,
                    frequency=freq,
                    is_resolved=False,
                    first_seen=now_ts - timedelta(weeks=3, days=2),
                    last_seen=now_ts - timedelta(days=5),
                )
                pattern_upserts += 1

        # ── Summary ──
        from collections import Counter
        state_counter = Counter(st for _id, st in created_session_ids)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Leera dogfood cohort — ready for the pitch"
        ))
        self.stdout.write("")
        self.stdout.write(
            f"Org:         {org.slug} (id={org.id})"
        )
        self.stdout.write(
            f"Cohort:      {cohort.name!r} (id={cohort.id})"
            + ("  [new]" if cohort_new else "  [existing]")
        )
        self.stdout.write(
            f"Course:      {course.name!r} (id={course.id})"
            + ("  [new]" if course_new else "  [existing]")
        )
        self.stdout.write(
            f"Rubric:      {rubric.name!r} (id={rubric.id})"
            + ("  [new]" if rubric_new else "  [existing]")
        )
        self.stdout.write(f"Teacher:     {teacher.email}")
        self.stdout.write(f"Students:    {len(STUDENTS)}")
        self.stdout.write("")
        self.stdout.write(f"GradingSessions: {len(created_session_ids)}")
        for st, n in sorted(state_counter.items()):
            self.stdout.write(f"  {st:<11} -> {n}")
        self.stdout.write("")
        self.stdout.write(f"SkillObservations bound: {skill_obs_count}")
        self.stdout.write(f"SkillMetric upserts:     {metric_upserts}")
        self.stdout.write(f"Pattern rows seeded:     {pattern_upserts}")
        self.stdout.write("")
        self.stdout.write("Session IDs by state:")
        for state_key in [
            GradingSession.State.PENDING,
            GradingSession.State.DRAFTING,
            GradingSession.State.DRAFTED,
            GradingSession.State.REVIEWING,
            GradingSession.State.POSTED,
            GradingSession.State.PARTIAL,
        ]:
            ids = [sid for sid, st in created_session_ids if st == state_key]
            if ids:
                self.stdout.write(f"  {state_key:<11}: {ids}")
        self.stdout.write("")
        self.stdout.write(
            f"Inbox URL:   http://localhost:5173/grading "
            f"(log in as {teacher.email})"
        )
