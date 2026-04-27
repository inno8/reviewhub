# Dogfood eval — May 15 data collection

This directory holds the data-collection scaffolding for the v0.9 → v1
validation dogfood scheduled for **May 15**. During the dogfood the
founder (and one volunteer docent) grade real MBO-4 ICT student PRs
using Nakijken Copilot and record:

- how long each session takes (stopwatch + manual log — cross-check)
- whether the rubric-level scores the AI produced match a human grader
- qualitative reflections at the end of each week

All files here are **templates**. They are intentionally empty /
stub-only until May 15. Workstreams I/J populate them during the
dogfood runs.

## Files


| File                             | Purpose                                                                                              |
| -------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `manual-timing-log.csv`          | Per-session stopwatch log. Cross-checked against `GradingSession.docent_review_time_seconds`.        |
| `rubric-accuracy-scoresheet.csv` | Per-session rubric-level accuracy vs. a human-graded reference. Shape mirrors `test_rubric_eval.py`. |
| `weekly-reflection-template.md`  | End-of-week qualitative reflection (what worked, what slowed me down, what I'd change).              |


## Fill-in rules

- One row per grading session (not per PR comment).
- Times in seconds, rounded to the nearest 5s.
- Rubric scores on the 1–4 scale from the built-in crebo 25187/25188 rubrics.
- Reflections are private — don't reference individual students by name.

## What "success" looks like at dogfood end

From the v1 success criteria:

- p50 review time ≤ 5 minutes per PR (target; v0 baseline is ~20 minutes)
- Rubric-level accuracy ≥ 70% (AI score within ±1 of human grader)
- At least one "I would keep using this" from the volunteer docent

If any of those miss, the v1 → v1.1 scope doc gets rewritten before the
June rollout.