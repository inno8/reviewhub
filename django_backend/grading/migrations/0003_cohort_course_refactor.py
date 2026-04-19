"""
Scope B1 / Workstream A — schema refactor:
  - Add Cohort model (the student-group licensing unit, €200/cohort/month).
  - Rename Classroom → Course (model + table).
  - Rename ClassroomMembership → CohortMembership (model + table).
  - Membership semantic change: student-per-cohort (OneToOne), not student-per-course.

Migration flow:
  1. Create Cohort table.
  2. Add nullable Course.cohort FK.
  3. RunPython:
       a. For each existing Classroom row, create a Cohort ("Name (auto)") and
          point classroom.cohort at it.
       b. FAIL LOUDLY (RuntimeError) if any student is in >1 classroom — the
          new schema allows only ONE cohort per student. The founder must
          resolve the conflict manually (merge or move members) and rerun.
       c. Copy ClassroomMembership rows into CohortMembership (student →
          cohort derived from the classroom's new auto-cohort).
  4. Rename Classroom → Course (model + db_table).
  5. Rename ClassroomMembership → CohortMembership; convert
     student FK → OneToOne (unique) on the new model.
  6. Clean up: rename Submission.classroom → Submission.course (FK column),
     rename LLMCostLog.classroom → LLMCostLog.course.

Notes:
  - This is a single migration file so it applies atomically and rolls back
    cleanly if the dupe-detection fires mid-stream.
  - We keep CohortMembership.student as OneToOneField (enforces uniqueness
    at the DB level — simpler than UniqueConstraint).
"""
from __future__ import annotations

from collections import defaultdict

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_classrooms_to_cohorts(apps, schema_editor):
    """
    Auto-create a Cohort per existing Classroom, migrate memberships.

    Fails loudly on any student that was in >1 classroom. The founder must
    resolve these (pick a target cohort per student, or merge classrooms)
    and re-apply the migration. No silent dedupe.
    """
    Classroom = apps.get_model("grading", "Classroom")
    Cohort = apps.get_model("grading", "Cohort")
    ClassroomMembership = apps.get_model("grading", "ClassroomMembership")

    # Step 1: detect student-in-multiple-classrooms BEFORE moving memberships.
    # A student allowed in only ONE cohort by the new schema; if they're in
    # 2+ classrooms today, the auto-migration cannot pick a winner for them.
    students_to_classrooms: dict[int, list[int]] = defaultdict(list)
    for cm in ClassroomMembership.objects.all():
        students_to_classrooms[cm.student_id].append(cm.classroom_id)

    conflicts = {
        sid: classrooms
        for sid, classrooms in students_to_classrooms.items()
        if len(classrooms) > 1
    }
    if conflicts:
        lines = [
            f"  student_id={sid} is in classrooms {classrooms}"
            for sid, classrooms in list(conflicts.items())[:20]
        ]
        raise RuntimeError(
            "Migration aborted: students are in multiple classrooms.\n"
            "The new schema allows exactly ONE cohort per student; the migration\n"
            "cannot auto-assign a winner. Resolve by removing the duplicate\n"
            "ClassroomMembership rows (or merging classrooms) in Django admin,\n"
            "then re-run `python manage.py migrate`.\n"
            f"Affected students ({len(conflicts)}):\n" + "\n".join(lines)
        )

    # Step 2: auto-create a Cohort per Classroom, link Course.cohort.
    classroom_to_cohort: dict[int, int] = {}
    for classroom in Classroom.objects.all():
        cohort = Cohort.objects.create(
            org=classroom.org,
            name=f"{classroom.name} (auto)",
        )
        classroom_to_cohort[classroom.id] = cohort.id
        classroom.cohort_id = cohort.id
        classroom.save(update_fields=["cohort"])

    # Step 3: stamp each ClassroomMembership with the auto-cohort in a
    # scratch field on the model. We can't yet write to a CohortMembership
    # table (doesn't exist yet — that's a later operation in this migration).
    # Instead we store the cohort_id on ClassroomMembership via a new nullable
    # column that later operations rename into place.
    # Simpler: we let the later RenameModel step carry the rows over, and use
    # a second RunPython at the end to re-point memberships at the cohort.
    # But that requires staging data in Python. Do it here: stash cohort_id
    # on each row via the `classroom.cohort_id` link so the later data-fill
    # step can read it.
    # (Nothing to do here — the renamed model will use classroom_id column
    # which we'll translate to cohort_id in the second RunPython.)


def backfill_cohort_on_memberships(apps, schema_editor):
    """
    After Rename(ClassroomMembership → CohortMembership) and the column
    rename (classroomid → cohort_id), each CohortMembership still has
    cohort_id pointing at the OLD Classroom row (now a Course). Translate
    those Course-ids into Cohort-ids via Course.cohort_id.
    """
    CohortMembership = apps.get_model("grading", "CohortMembership")
    Course = apps.get_model("grading", "Course")

    course_to_cohort: dict[int, int] = dict(
        Course.objects.values_list("id", "cohort_id")
    )
    for m in CohortMembership.objects.all():
        # At this point m.cohort_id actually holds the old classroom id
        # (now course id). Translate it into the cohort id.
        real_cohort_id = course_to_cohort.get(m.cohort_id)
        if real_cohort_id is None:
            raise RuntimeError(
                f"CohortMembership {m.id} references course {m.cohort_id} "
                "which has no cohort — migration invariant violated."
            )
        if m.cohort_id != real_cohort_id:
            m.cohort_id = real_cohort_id
            m.save(update_fields=["cohort"])


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0002_rename_classmembership_classroommembership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── 1. Create Cohort ────────────────────────────────────────────
        migrations.CreateModel(
            name="Cohort",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("year", models.CharField(blank=True, max_length=20)),
                ("starts_at", models.DateField(blank=True, null=True)),
                ("ends_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cohorts",
                        to="users.organization",
                    ),
                ),
            ],
            options={
                "db_table": "grading_cohorts",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["org", "-created_at"], name="grading_coh_org_id_3bf724_idx"),
                ],
            },
        ),

        # ── 2. Add Classroom.cohort FK (nullable during transition) ─────
        migrations.AddField(
            model_name="classroom",
            name="cohort",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classrooms_pending_rename",
                to="grading.cohort",
                help_text="Cohort this course belongs to.",
            ),
        ),

        # ── 3. Auto-create Cohort per Classroom + fail on duplicate students ──
        migrations.RunPython(
            migrate_classrooms_to_cohorts,
            reverse_code=migrations.RunPython.noop,
        ),

        # ── 4. Rename Classroom → Course ────────────────────────────────
        migrations.RenameModel(old_name="Classroom", new_name="Course"),
        migrations.AlterModelOptions(
            name="course",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterModelTable(
            name="course",
            table="grading_courses",
        ),
        migrations.AlterField(
            model_name="course",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="courses",
                to="users.organization",
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="owner",
            field=models.ForeignKey(
                help_text="Primary docent. Must have role=TEACHER.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="owned_courses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="secondary_docent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="secondary_courses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="rubric",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="courses_using",
                to="grading.rubric",
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="cohort",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="courses",
                to="grading.cohort",
                help_text="Cohort (klas) this course belongs to. Nullable during initial migration; application-level code treats it as required post-migration.",
            ),
        ),
        migrations.AddIndex(
            model_name="course",
            index=models.Index(fields=["cohort", "-created_at"], name="grading_cou_cohort__5c9555_idx"),
        ),
        migrations.RenameIndex(
            model_name="course",
            old_name="grading_cla_org_id_d893f3_idx",
            new_name="grading_cou_org_id_eca565_idx",
        ),

        # ── 5. Rename ClassroomMembership → CohortMembership ───────────
        migrations.RenameModel(old_name="ClassroomMembership", new_name="CohortMembership"),
        migrations.AlterModelTable(
            name="cohortmembership",
            table="grading_cohort_memberships",
        ),
        # Rename the FK field classroom → cohort. At this point the row still
        # holds the old classroom-id (now course-id); we'll translate after.
        migrations.RenameField(
            model_name="cohortmembership",
            old_name="classroom",
            new_name="cohort",
        ),
        migrations.AlterField(
            model_name="cohortmembership",
            name="cohort",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="memberships",
                to="grading.cohort",
            ),
        ),
        # Drop the old unique_together before switching student to OneToOne
        migrations.AlterUniqueTogether(
            name="cohortmembership",
            unique_together=set(),
        ),
        migrations.AlterModelOptions(
            name="cohortmembership",
            options={"ordering": ["cohort", "student"]},
        ),

        # ── 6. Backfill cohort_id on memberships (course-id → cohort-id) ──
        migrations.RunPython(
            backfill_cohort_on_memberships,
            reverse_code=migrations.RunPython.noop,
        ),

        # ── 7. Student → OneToOne (enforces one cohort per student) ────
        migrations.AlterField(
            model_name="cohortmembership",
            name="student",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cohort_membership",
                to=settings.AUTH_USER_MODEL,
                help_text="A student belongs to exactly one cohort. Enforced at the DB level via OneToOne.",
            ),
        ),
        migrations.AlterField(
            model_name="cohortmembership",
            name="student_repo_url",
            field=models.URLField(
                blank=True,
                null=True,
                help_text="Student's chosen repo URL for this cohort (e.g., github.com/jandeboer/assignment-q3).",
            ),
        ),

        # ── 8. Submission.classroom → course ───────────────────────────
        # Drop the old index + unique_together referencing classroom FIRST,
        # before SQLite rebuilds the table during the rename/alter steps.
        migrations.RemoveIndex(
            model_name="submission",
            name="grading_sub_org_id_2ca3dc_idx",
        ),
        migrations.AlterUniqueTogether(
            name="submission",
            unique_together=set(),
        ),
        migrations.RenameField(
            model_name="submission",
            old_name="classroom",
            new_name="course",
        ),
        migrations.AlterUniqueTogether(
            name="submission",
            unique_together={("course", "repo_full_name", "pr_number")},
        ),
        migrations.AlterField(
            model_name="submission",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="submissions",
                to="grading.course",
            ),
        ),
        migrations.AddIndex(
            model_name="submission",
            index=models.Index(fields=["org", "course", "status"], name="grading_sub_org_id_8d2d8a_idx"),
        ),

        # ── 9. LLMCostLog.classroom → course ───────────────────────────
        migrations.RemoveIndex(
            model_name="llmcostlog",
            name="grading_llm_classro_b3c731_idx",
        ),
        migrations.RenameField(
            model_name="llmcostlog",
            old_name="classroom",
            new_name="course",
        ),
        migrations.AlterField(
            model_name="llmcostlog",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="llm_cost_logs",
                to="grading.course",
            ),
        ),
        migrations.AddIndex(
            model_name="llmcostlog",
            index=models.Index(fields=["course", "occurred_at"], name="grading_llm_course__6a91f8_idx"),
        ),
    ]
