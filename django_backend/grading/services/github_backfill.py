"""
GitHub historical PR backfill helpers — Workstream H (Leera v0.9 dogfood).

Fetches merged PRs from a GitHub repo via the REST API and exposes a small
Layer-1 deterministic analyzer that produces DeterministicFinding-shaped
dicts from a PR's patch text. No LLM calls — the whole point of backfill
is cheap seed data for the May 7 pitch day growth-arc demo.

Caller (management command) is responsible for persistence + idempotency
via Submission.pr_url.

v1 simplifications (documented for future hardening):
  * Deterministic runner is regex-based (long lines, TODO/FIXME, bare
    except, console.log, trailing whitespace). Good enough to seed the
    growth arc; the real ruff/ESLint runners are Day 2 of Scope B2 and
    live in ai_engine/.
  * Skill mapping is heuristic — each rule maps to at most 1 skill slug.
    If the skill doesn't exist on the system (fresh DB) we silently skip
    the SkillObservation side-effect; findings are still recorded.
  * Contribution fraction is always 1.0 for the primary author — backfill
    seeds ONE student's profile, we never fan out across co-contributors.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests

log = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 20
_PER_PAGE = 100


class BackfillError(Exception):
    """Non-transient error that should stop the backfill with a clear message."""


# ─────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────
def get_token() -> str:
    """Read PAT from env. Fail fast with a clear message."""
    token = (os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or "").strip()
    if not token:
        raise BackfillError(
            "GITHUB_PERSONAL_ACCESS_TOKEN env var not set. "
            "Create a PAT with `repo` scope and export it before running backfill."
        )
    return token


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ─────────────────────────────────────────────────────────────────────
# GitHub fetch primitives
# ─────────────────────────────────────────────────────────────────────
def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    # GitHub returns "2026-01-15T14:30:00Z"
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _next_link(resp) -> Optional[str]:
    link = resp.headers.get("Link") or ""
    # rel="next" header parsing
    for part in link.split(","):
        seg = part.strip()
        if 'rel="next"' in seg:
            m = re.search(r"<([^>]+)>", seg)
            if m:
                return m.group(1)
    return None


def iter_merged_prs(
    repo: str,
    *,
    token: str,
    cutoff: Optional[datetime] = None,
    session: Optional[requests.Session] = None,
) -> Iterable[dict]:
    """
    Yield merged PRs newest-first, stopping when updated_at < cutoff.
    Only PRs where `merged_at` is not null are yielded.
    """
    sess = session or requests
    url = (
        f"{_GITHUB_API}/repos/{repo}/pulls"
        f"?state=closed&sort=updated&direction=desc&per_page={_PER_PAGE}"
    )
    while url:
        resp = sess.get(url, headers=_headers(token), timeout=_TIMEOUT)
        if resp.status_code == 404:
            raise BackfillError(f"Repo '{repo}' not found or PAT lacks access.")
        if resp.status_code == 401:
            raise BackfillError("GitHub rejected PAT (401). Check token scopes.")
        if resp.status_code >= 400:
            raise BackfillError(
                f"GitHub API error {resp.status_code} fetching {url}: "
                f"{resp.text[:200]}"
            )

        items = resp.json() or []
        for pr in items:
            if not pr.get("merged_at"):
                continue
            updated = _parse_iso(pr.get("updated_at"))
            if cutoff and updated and updated < cutoff:
                return
            yield pr

        # Follow pagination, but short-circuit if last item on page is past cutoff
        if items and cutoff:
            last_updated = _parse_iso(items[-1].get("updated_at"))
            if last_updated and last_updated < cutoff:
                return
        url = _next_link(resp)


def fetch_pr_files(repo: str, pr_number: int, *, token: str, session=None) -> list[dict]:
    """GET /repos/{repo}/pulls/{n}/files — returns list of file dicts."""
    sess = session or requests
    url = f"{_GITHUB_API}/repos/{repo}/pulls/{pr_number}/files?per_page=100"
    out: list[dict] = []
    while url:
        resp = sess.get(url, headers=_headers(token), timeout=_TIMEOUT)
        if resp.status_code >= 400:
            raise BackfillError(
                f"fetch_pr_files({repo}#{pr_number}) HTTP {resp.status_code}: "
                f"{resp.text[:200]}"
            )
        out.extend(resp.json() or [])
        url = _next_link(resp)
    return out


# ─────────────────────────────────────────────────────────────────────
# Layer 1 deterministic analyzer (regex-based; no external tools)
# ─────────────────────────────────────────────────────────────────────
@dataclass
class DetFinding:
    runner: str            # 'ruff' or 'eslint'
    rule_id: str
    message: str
    severity: str          # 'info' | 'warning' | 'critical' | 'suggestion'
    file_path: str
    line_start: int
    line_end: int
    skill_slug: Optional[str] = None  # soft mapping to a Skill.slug for SkillObservation

    def as_kwargs(self) -> dict:
        return {
            "runner": self.runner,
            "rule_id": self.rule_id,
            "message": self.message,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


# Rule table — (regex, rule_id, runner, severity, message, skill_slug)
_PY_RULES = [
    (re.compile(r"^\+.{101,}$"), "E501", "ruff", "info",
     "Line too long (>100 chars)", "clean_code"),
    (re.compile(r"^\+.*\bexcept\s*:\s*$"), "E722", "ruff", "warning",
     "Do not use bare except", "error_handling"),
    (re.compile(r"^\+.*\b(TODO|FIXME|XXX)\b"), "T001", "ruff", "suggestion",
     "TODO/FIXME comment in committed code", "clean_code"),
    (re.compile(r"^\+.*\bprint\("), "T201", "ruff", "info",
     "print() left in code", "clean_code"),
    (re.compile(r"^\+.*\s+$"), "W291", "ruff", "suggestion",
     "Trailing whitespace", "clean_code"),
]

_JS_RULES = [
    (re.compile(r"^\+.*console\.log\("), "no-console", "eslint", "info",
     "Unexpected console.log", "clean_code"),
    (re.compile(r"^\+.*\bvar\s+\w+"), "no-var", "eslint", "warning",
     "Use let/const instead of var", "clean_code"),
    (re.compile(r"^\+.*==[^=]"), "eqeqeq", "eslint", "warning",
     "Use === instead of ==", "clean_code"),
    (re.compile(r"^\+.{121,}$"), "max-len", "eslint", "info",
     "Line too long (>120 chars)", "clean_code"),
    (re.compile(r"^\+.*\b(TODO|FIXME|XXX)\b"), "no-warning-comments",
     "eslint", "suggestion",
     "TODO/FIXME comment in committed code", "clean_code"),
]

_PHP_RULES = [
    (re.compile(r"^\+.*\bvar_dump\("), "Generic.Debug", "eslint", "warning",
     "var_dump() left in code", "clean_code"),
    (re.compile(r"^\+.*\bdie\("), "Generic.Debug.Die", "eslint", "critical",
     "die()/exit() in production code path", "error_handling"),
]


def _pick_rules(filename: str):
    low = filename.lower()
    if low.endswith(".py"):
        return _PY_RULES
    if low.endswith((".js", ".jsx", ".ts", ".tsx", ".vue")):
        return _JS_RULES
    if low.endswith(".php"):
        return _PHP_RULES
    return []


def analyze_patch(filename: str, patch: Optional[str]) -> list[DetFinding]:
    """
    Scan a unified-diff patch for deterministic findings.

    We track diff line numbers by walking @@ hunks and counting '+' lines
    against the new-file line counter. Context lines also advance the
    counter. Removed '-' lines do not.
    """
    if not patch:
        return []
    rules = _pick_rules(filename)
    if not rules:
        return []

    findings: list[DetFinding] = []
    new_line = 0
    hunk_re = re.compile(r"^@@ .* \+(\d+)(?:,(\d+))? @@")

    for raw in patch.splitlines():
        if raw.startswith("@@"):
            m = hunk_re.match(raw)
            if m:
                new_line = int(m.group(1)) - 1
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            new_line += 1
            for pattern, rule_id, runner, severity, msg, skill in rules:
                if pattern.match(raw):
                    findings.append(DetFinding(
                        runner=runner, rule_id=rule_id, message=msg,
                        severity=severity, file_path=filename,
                        line_start=new_line, line_end=new_line,
                        skill_slug=skill,
                    ))
        elif raw.startswith("-"):
            pass
        else:
            # context line
            new_line += 1
    return findings


# ─────────────────────────────────────────────────────────────────────
# Aggregate PR -> diff-level summary (for Evaluation row)
# ─────────────────────────────────────────────────────────────────────
@dataclass
class PRAnalysis:
    pr: dict
    files: list[dict]
    findings: list[DetFinding] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0

    @property
    def quality_score(self) -> float:
        """
        Crude but useful quality heuristic: start at 85, deduct per finding
        weighted by severity. Clamped to [0, 100]. The backfill is seeding
        a growth arc, so variability across PRs is what matters — exact
        calibration against LLM scores isn't.
        """
        penalty_per = {"critical": 8, "warning": 3, "info": 1, "suggestion": 0.5}
        penalty = sum(penalty_per.get(f.severity, 1) for f in self.findings)
        # density normalization: big PRs shouldn't be disproportionately punished
        touched = max(self.lines_added + self.lines_removed, 20)
        normalized = penalty * 20.0 / touched
        return max(0.0, min(100.0, round(85.0 - normalized, 2)))

    @property
    def complexity_weight(self) -> float:
        total = self.lines_added + self.lines_removed
        if total >= 200:
            return 1.0
        if total >= 50:
            return 0.7
        return 0.4


def analyze_pr(pr: dict, files: list[dict]) -> PRAnalysis:
    analysis = PRAnalysis(pr=pr, files=files)
    for f in files:
        analysis.lines_added += int(f.get("additions") or 0)
        analysis.lines_removed += int(f.get("deletions") or 0)
        analysis.findings.extend(
            analyze_patch(f.get("filename") or "", f.get("patch"))
        )
    return analysis
