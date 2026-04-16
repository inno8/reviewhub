"""
Commit Complexity Classifier — deterministic, zero-I/O heuristic scoring.

Runs BEFORE any LLM call and classifies each commit as simple / medium / complex.
The resulting CommitComplexity object controls:
  - which model tier to use (cheap / lighter / org-default)
  - how much context to send (0 / 3 / 5 related files)
  - max_tokens cap (1024 / 2048 / 4096)
  - learning weight for skill/pattern updates (0.3 / 0.7 / 1.0)

Scoring layers (adapted from docs/Rule_Based_Heuristics.txt):
  Layer 1 — lines changed  : score += total_lines / 50
  Layer 2 — files changed  : score += files * 2
  Layer 3 — commit message : keyword bonuses / penalties
  Layer 4 — file types     : +1 per non-trivial source file
  Layer 5 — security paths : +3 if any path touches auth / payment / crypto
  Layer 6 — user patterns  : +3 if profile signals recurring complex struggles

Thresholds:
  score < 5   → simple
  5 ≤ score < 15 → medium
  score ≥ 15  → complex
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SIMPLE_THRESHOLD = 5.0
COMPLEX_THRESHOLD = 15.0

# Commit message keyword bonuses (case-insensitive match anywhere in message)
MESSAGE_BONUSES: dict[str, float] = {
    "refactor": 5.0,
    "feature":  4.0,
    "feat":     4.0,
    "breaking": 5.0,
    "migration": 4.0,
    "security": 4.0,
    "hotfix":   2.0,
    "fix":      2.0,
    "bugfix":   2.0,
    "perf":     2.0,
    "optimize": 2.0,
}

MESSAGE_PENALTIES: dict[str, float] = {
    "typo":    -2.0,
    "docs":    -2.0,
    "readme":  -2.0,
    "wip":     -1.0,
    "minor":   -1.0,
    "bump":    -1.0,
    "version": -1.0,
    "chore":   -1.0,
    "style":   -1.0,
    "format":  -1.0,
}

# File extensions that contribute +1 each (non-trivial source code)
NONTRIVIAL_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".vue", ".go", ".java", ".rs", ".rb",
    ".php", ".cpp", ".c", ".cs", ".kt",
    ".swift", ".scala",
}

# File extensions / names that contribute 0 (docs / config / generated)
TRIVIAL_EXTENSIONS = {
    ".md", ".txt", ".rst", ".css", ".scss",
    ".sass", ".less", ".lock", ".json",
    ".yaml", ".yml", ".toml", ".ini",
    ".env", ".gitignore", ".editorconfig",
    ".min.js", ".min.css", ".pyc", ".bin",
    ".png", ".jpg", ".jpeg", ".svg", ".gif",
}

# Path fragments that indicate security-sensitive changes
SECURITY_PATH_SIGNALS = {
    "auth", "authentication", "authorization",
    "security", "payment", "billing",
    "crypto", "encrypt", "decrypt",
    "token", "credential", "secret",
    "permission", "role", "oauth",
    "password", "hash",
}

# Pattern keys in user profile that indicate complex-struggle history
COMPLEX_STRUGGLE_PATTERNS = {
    "missing_edge_cases",
    "poor_error_handling",
    "no_input_validation",
    "security_exposure",
    "performance_issues",
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CommitComplexity:
    """Result of classifying a single commit."""
    level: str               # "simple" | "medium" | "complex"
    score: float             # raw numeric score
    reasons: list[str] = field(default_factory=list)

    # Derived routing parameters (set from level)
    max_tokens: int = 2048
    context_file_limit: int = 3
    learning_weight: float = 0.7

    def __post_init__(self):
        self.max_tokens, self.context_file_limit, self.learning_weight = _level_params(self.level)

    @property
    def is_simple(self) -> bool:
        return self.level == "simple"

    @property
    def is_complex(self) -> bool:
        return self.level == "complex"


def _level_params(level: str) -> tuple[int, int, float]:
    """Return (max_tokens, context_file_limit, learning_weight) for a level."""
    if level == "simple":
        return 1024, 0, 0.3
    if level == "complex":
        return 4096, 5, 1.0
    return 2048, 3, 0.7   # medium


def _classify_score(score: float) -> str:
    if score < SIMPLE_THRESHOLD:
        return "simple"
    if score < COMPLEX_THRESHOLD:
        return "medium"
    return "complex"


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class CommitClassifier:
    """
    Zero-dependency, synchronous commit complexity classifier.

    Usage:
        classifier = CommitClassifier()
        complexity = classifier.classify(diff_data, commit_meta, profile)
    """

    def classify(
        self,
        diff_data: dict,
        commit_meta: dict,
        profile: Optional[dict] = None,
    ) -> CommitComplexity:
        """
        Classify a commit.

        Args:
            diff_data: dict with keys:
                - "files": list of file-diff dicts (each has "path", "additions",
                  "deletions", "diff", "language")
                - "lines_added": int
                - "lines_removed": int
            commit_meta: dict with at least:
                - "message": str   (commit message)
                - "sha" or "id":   str (for logging)
            profile: developer adaptive profile dict from Django
                (same shape as AdaptiveProfile / build_developer_history_section)

        Returns:
            CommitComplexity
        """
        score = 0.0
        reasons: list[str] = []

        files: list[dict] = diff_data.get("files") or []
        lines_added = int(diff_data.get("lines_added") or 0)
        lines_removed = int(diff_data.get("lines_removed") or 0)

        # Fallback: sum from file diffs when top-level totals are absent
        if lines_added == 0 and lines_removed == 0 and files:
            lines_added = sum(f.get("additions", 0) for f in files)
            lines_removed = sum(f.get("deletions", 0) for f in files)

        total_lines = lines_added + lines_removed
        file_count = len(files)

        # ── Layer 1: Lines changed ────────────────────────────────────────
        line_score = total_lines / 50.0
        score += line_score
        if line_score >= 1:
            reasons.append(f"lines={total_lines} (+{line_score:.1f})")

        # ── Layer 2: Files changed ────────────────────────────────────────
        file_score = file_count * 2.0
        score += file_score
        if file_count > 1:
            reasons.append(f"files={file_count} (+{file_score:.1f})")

        # ── Layer 3: Commit message keywords ─────────────────────────────
        msg = (commit_meta.get("message") or "").lower()
        msg_delta = 0.0
        for kw, bonus in MESSAGE_BONUSES.items():
            if kw in msg:
                msg_delta += bonus
                reasons.append(f"keyword:{kw} (+{bonus})")
                break  # take the largest match only (first)
        for kw, penalty in MESSAGE_PENALTIES.items():
            if kw in msg:
                msg_delta += penalty
                reasons.append(f"keyword:{kw} ({penalty})")
                break
        score += msg_delta

        # ── Layer 4: File type weights ────────────────────────────────────
        type_score = 0.0
        for fd in files:
            path = (fd.get("path") or "").lower()
            ext = _extension(path)
            if ext in NONTRIVIAL_EXTENSIONS:
                type_score += 1.0
            # trivial extensions add 0
        score += type_score
        if type_score > 0:
            reasons.append(f"source_files={int(type_score)} (+{type_score:.1f})")

        # ── Layer 5a (G4/G7): Diff quality — structural vs. cosmetic ─────
        # Detect if the diff is mostly whitespace/formatting changes
        structural_lines = 0
        cosmetic_lines = 0
        for fd in files:
            diff_text = fd.get("diff", "")
            for line in diff_text.splitlines():
                if not line.startswith("+") or line.startswith("+++"):
                    continue
                stripped = line[1:].strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                    cosmetic_lines += 1
                elif stripped in ("}", ")", "]", "{", "(", "[", "pass", "end"):
                    cosmetic_lines += 1
                else:
                    structural_lines += 1

        total_diff_lines = structural_lines + cosmetic_lines
        if total_diff_lines > 0:
            structural_ratio = structural_lines / total_diff_lines
            if structural_ratio < 0.3 and total_lines > 20:
                # Mostly cosmetic — reduce complexity score
                penalty = -3.0
                score += penalty
                reasons.append(f"cosmetic_ratio={1-structural_ratio:.0%} ({penalty})")
            elif structural_ratio > 0.8 and structural_lines > 30:
                bonus = 2.0
                score += bonus
                reasons.append(f"structural_ratio={structural_ratio:.0%} (+{bonus})")

        # ── Layer 6: Security-sensitive paths ─────────────────────────────
        security_hit = False
        for fd in files:
            path = (fd.get("path") or "").lower()
            for sig in SECURITY_PATH_SIGNALS:
                if sig in path:
                    security_hit = True
                    break
            if security_hit:
                break
        if security_hit:
            score += 3.0
            reasons.append("security-sensitive path (+3.0)")

        # ── Layer 6: User pattern history ─────────────────────────────────
        if _has_complex_struggles(profile):
            score += 3.0
            reasons.append("user has recurring complex struggles (+3.0)")

        level = _classify_score(score)
        return CommitComplexity(level=level, score=round(score, 2), reasons=reasons)


# ---------------------------------------------------------------------------
# Profile helper (also exported for use by adaptive_profile.py / tests)
# ---------------------------------------------------------------------------

def has_complex_struggles(profile: Optional[dict]) -> bool:
    """
    Return True if the developer profile signals recurring complex issues.
    Exported so tests and adaptive_profile.py can call it directly.
    """
    return _has_complex_struggles(profile)


def _has_complex_struggles(profile: Optional[dict]) -> bool:
    if not profile:
        return False

    weaknesses = profile.get("weaknesses") or []
    if len(weaknesses) >= 3:
        return True

    frequent_patterns = profile.get("frequent_patterns") or []
    complex_pattern_count = sum(
        1 for p in frequent_patterns
        if _pattern_base(p.get("pattern_key", "")) in COMPLEX_STRUGGLE_PATTERNS
        and p.get("count", 0) >= 2
    )
    if complex_pattern_count >= 2:
        return True

    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extension(path: str) -> str:
    """Return the file extension including the dot, lower-cased."""
    if "." not in path:
        return ""
    return "." + path.rsplit(".", 1)[-1]


def _pattern_base(key: str) -> str:
    """Strip severity suffix: 'error_handling:warning' → 'error_handling'."""
    return key.split(":")[0] if ":" in key else key
