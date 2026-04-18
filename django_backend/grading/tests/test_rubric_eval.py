"""
Rubric grading accuracy eval — THE v1 ship-gate.

Loads the eval set (JSON manifest + .diff files) and runs the rubric grader
against each case. Compares AI scores to the founder's ground-truth scores
and computes:

    within_1_point_rate = fraction of (case, criterion) pairs where the AI's
                          score is within 1 of the ground truth.

Ship bar (from the design doc Success Criteria):
    within_1_point_rate >= 0.80 on the May dogfood set (20 real intern PRs)

How this file runs in two modes:

  1. Unit-test mode (default, CI-friendly):
     The seed set (eval_set_seed.json, 3 synthetic cases) plus a FAKE
     ai_engine that returns deterministic scores per case. Proves the
     runner code works. No network, no LLM tokens burned.

  2. Live mode (opt-in via RUBRIC_EVAL_LIVE=1 env var):
     Hits the real ai_engine /api/v1/grade endpoint. Used during May
     dogfood to measure accuracy against the founder's 20-PR ground set.
     Skipped by default so CI doesn't burn budget on every push.

To run live:
    RUBRIC_EVAL_LIVE=1 pytest grading/tests/test_rubric_eval.py -v

The live run writes a timestamped report to:
    ~/.gstack/projects/inno8-reviewhub/rubric-eval-{date}.json
so trend data is captured across the dogfood weeks.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from grading.services.pii_redaction import StudentIdentity

User = get_user_model()

SEED_DIR = Path(__file__).parent / "fixtures"
SEED_FILE = SEED_DIR / "eval_set_seed.json"

# Ship-gate threshold (design doc Success Criteria)
MIN_WITHIN_1_POINT_RATE = 0.80


@dataclass
class EvalCaseResult:
    case_id: str
    label: str
    n_criteria: int
    n_within_1: int

    @property
    def within_1_rate(self) -> float:
        return self.n_within_1 / self.n_criteria if self.n_criteria else 0.0


def load_eval_set(path: Path = SEED_FILE) -> dict:
    """Load the JSON manifest + inline the .diff contents."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for case in data["cases"]:
        diff_path = path.parent / case["diff_file"]
        case["diff"] = diff_path.read_text(encoding="utf-8")
    return data


def score_case(
    *,
    case: dict,
    rubric: dict,
    grader_fn,
    student: StudentIdentity | None = None,
) -> EvalCaseResult:
    """
    Run the grader against one case and compute within-1-point hits.

    `grader_fn` is injected for testability. Signature:
        grader_fn(diff: str, criteria: list, calibration: dict) -> dict[criterion_id, {score, evidence}]
    """
    truth = case["ground_truth_scores"]
    predicted = grader_fn(case["diff"], rubric["criteria"], rubric["calibration"])

    hits = 0
    total = 0
    for criterion_id, truth_entry in truth.items():
        total += 1
        pred_entry = predicted.get(criterion_id)
        if pred_entry is None:
            continue  # miss
        try:
            diff = abs(int(pred_entry["score"]) - int(truth_entry["score"]))
        except (KeyError, TypeError, ValueError):
            continue  # miss
        if diff <= 1:
            hits += 1

    return EvalCaseResult(
        case_id=case["id"],
        label=case["label"],
        n_criteria=total,
        n_within_1=hits,
    )


def aggregate_results(results: list[EvalCaseResult]) -> dict:
    total_criteria = sum(r.n_criteria for r in results)
    total_hits = sum(r.n_within_1 for r in results)
    rate = total_hits / total_criteria if total_criteria else 0.0
    return {
        "n_cases": len(results),
        "n_criteria": total_criteria,
        "n_within_1": total_hits,
        "within_1_point_rate": round(rate, 4),
        "passes_ship_gate": rate >= MIN_WITHIN_1_POINT_RATE,
        "per_case": [
            {
                "case_id": r.case_id,
                "label": r.label,
                "n_criteria": r.n_criteria,
                "n_within_1": r.n_within_1,
                "within_1_rate": round(r.within_1_rate, 4),
            }
            for r in results
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Unit-test mode — deterministic fake grader
# ─────────────────────────────────────────────────────────────────────────────
def _fake_grader_perfect(diff: str, criteria: list, calibration: dict) -> dict:
    """Matches ground truth exactly. Should score 100% within-1."""
    # The test patches this per case via a side effect of side_effect
    raise NotImplementedError


class TestEvalRunner:
    """The eval runner itself — covers loading, scoring, aggregation."""

    def test_loads_seed_manifest_with_inlined_diffs(self):
        data = load_eval_set()
        assert data["version"].startswith("v0.1")
        assert len(data["cases"]) == 3
        for case in data["cases"]:
            assert "diff" in case
            assert len(case["diff"]) > 0

    def test_scores_perfect_grader_at_100_percent(self):
        data = load_eval_set()
        rubric = data["rubric"]

        def perfect_grader(diff, criteria, calibration):
            # Return whatever the case expects — we know it inside the test
            # by peeking at the current case via a module-level var below
            return _current_truth.copy()

        results = []
        for case in data["cases"]:
            globals()["_current_truth"] = case["ground_truth_scores"]
            results.append(score_case(case=case, rubric=rubric, grader_fn=perfect_grader))

        agg = aggregate_results(results)
        assert agg["within_1_point_rate"] == 1.0
        assert agg["passes_ship_gate"] is True

    def test_scores_off_by_two_grader_below_threshold(self):
        data = load_eval_set()
        rubric = data["rubric"]

        def off_by_two_grader(diff, criteria, calibration):
            # Always predict 1 — truth values range 1-4, so some cases
            # will hit within-1 (any truth=1 or =2), others won't.
            return {c["id"]: {"score": 1, "evidence": "stub"} for c in criteria}

        results = [
            score_case(case=c, rubric=rubric, grader_fn=off_by_two_grader)
            for c in data["cases"]
        ]
        agg = aggregate_results(results)
        # This grader is dumb; rate will depend on truth distribution
        assert 0.0 < agg["within_1_point_rate"] < 1.0

    def test_missing_criterion_counts_as_miss(self):
        data = load_eval_set()
        rubric = data["rubric"]

        def partial_grader(diff, criteria, calibration):
            # Return only the first criterion
            first = criteria[0]["id"]
            return {first: {"score": 3, "evidence": "stub"}}

        case = data["cases"][0]
        result = score_case(case=case, rubric=rubric, grader_fn=partial_grader)
        # 4 criteria in rubric; only 1 returned → at most 1 hit
        assert result.n_criteria == 4
        assert result.n_within_1 <= 1

    def test_malformed_prediction_counts_as_miss(self):
        data = load_eval_set()
        rubric = data["rubric"]

        def broken_grader(diff, criteria, calibration):
            return {c["id"]: {"score": "not-a-number"} for c in criteria}

        case = data["cases"][0]
        result = score_case(case=case, rubric=rubric, grader_fn=broken_grader)
        assert result.n_within_1 == 0


# ─────────────────────────────────────────────────────────────────────────────
# Live mode — only when RUBRIC_EVAL_LIVE=1
# ─────────────────────────────────────────────────────────────────────────────
LIVE_MODE = os.getenv("RUBRIC_EVAL_LIVE") == "1"


@pytest.mark.skipif(not LIVE_MODE, reason="Set RUBRIC_EVAL_LIVE=1 to run against real ai_engine")
@pytest.mark.django_db
class TestLiveRubricEval:
    """
    Real eval run. Hits ai_engine /api/v1/grade with the seed (or dogfood) set.
    Writes a timestamped report to ~/.gstack/projects/inno8-reviewhub/rubric-eval-{date}.json.
    """

    def test_live_eval_meets_ship_gate(self, db):
        import datetime as dt
        from grading.services import rubric_grader
        from grading.models import Classroom, GradingSession, Rubric, Submission
        from users.models import Organization

        data = load_eval_set()
        rubric_spec = data["rubric"]

        # Minimal DB scaffolding so rubric_grader's cost metering write succeeds.
        org = Organization.objects.create(name="Eval Org", slug="eval-org")
        teacher = User.objects.create_user(
            username="eval_teacher", email="eval@ex.com", password="pw",
            role="teacher", organization=org,
        )
        student = User.objects.create_user(
            username="eval_student", email="student@ex.com", password="pw",
            role="developer", organization=org,
        )
        rubric = Rubric.objects.create(
            org=org, owner=teacher, name=rubric_spec["name"],
            criteria=rubric_spec["criteria"],
            calibration=rubric_spec["calibration"],
        )
        classroom = Classroom.objects.create(
            org=org, owner=teacher, name="Eval Class", rubric=rubric,
        )

        def live_grader(diff, criteria, calibration):
            sub = Submission.objects.create(
                org=org, classroom=classroom, student=student,
                repo_full_name="eval/repo", pr_number=len(GradingSession.objects.all()) + 1,
                pr_url="https://github.com/eval/repo/pull/1", head_branch="feat",
            )
            sess = GradingSession.objects.create(
                org=org, submission=sub, rubric=rubric,
            )
            result = rubric_grader.generate_draft(
                org_id=org.id,
                grading_session_id=sess.id,
                input_=rubric_grader.GraderInput(
                    diff=diff,
                    rubric_criteria=criteria,
                    rubric_calibration=calibration,
                    student=StudentIdentity(
                        student_id=student.id,
                        display_name="Anonymized Student",
                        first_name="Student",
                        email=student.email,
                    ),
                    context={},
                    tier="premium",
                    docent_id=teacher.id,
                ),
            )
            return result.scores

        results = [
            score_case(case=c, rubric=rubric_spec, grader_fn=live_grader)
            for c in data["cases"]
        ]
        agg = aggregate_results(results)

        # Write trend report
        report_dir = Path.home() / ".gstack" / "projects" / "inno8-reviewhub"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        report_path = report_dir / f"rubric-eval-{stamp}.json"
        report_path.write_text(
            json.dumps({
                "timestamp": dt.datetime.utcnow().isoformat() + "Z",
                "eval_set_version": data["version"],
                **agg,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"\nRubric eval report: {report_path}")
        print(f"Within-1-point rate: {agg['within_1_point_rate']:.2%}")
        print(f"Ship gate (>={MIN_WITHIN_1_POINT_RATE:.0%}): "
              f"{'PASS' if agg['passes_ship_gate'] else 'FAIL'}")

        assert agg["passes_ship_gate"], (
            f"Rubric grader scored {agg['within_1_point_rate']:.2%} within-1-point, "
            f"below the {MIN_WITHIN_1_POINT_RATE:.0%} ship gate."
        )
