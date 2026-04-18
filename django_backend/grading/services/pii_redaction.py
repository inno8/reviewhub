"""
PII redaction + rehydration for LLM calls.

Per eng review, v1 ships with FULL redaction: name + email + GitHub handle
replaced with stable pseudonyms (Student-A, Student-B, ...) before the diff
or context is sent to the LLM. After the LLM returns, we rehydrate the
pseudonyms back to the student's display name.

Why: AVG/GDPR compliance for MBO-4 minors. LLM providers (Anthropic, OpenAI)
retain API payloads for up to 30 days. We never send identifiable data about
Dutch minors into that retention window.

Edge cases handled (per test plan):
  - Names with regex specials: "O'Brien", "De Vries-van Dam", "Janssen, Jr."
  - Handles appearing inside URLs (github.com/handle/repo)
  - Null name → fall back to handle-only redaction
  - Rehydration: if LLM paraphrased away the pseudonym, flag it (CEO-review
    finding #10: "LLM dropped the placeholder" regression).

The pseudonym map is deterministic per-session so the same student always
gets the same pseudonym within one grading session, but pseudonyms do NOT
persist across sessions (defense in depth vs. LLM memory).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class StudentIdentity:
    """Minimal identity struct for redaction. Avoid coupling to User model
    so tests can construct these without a DB."""

    student_id: int
    display_name: str  # e.g., "Jan de Boer"
    first_name: str = ""
    email: str = ""
    github_handle: str = ""
    gitlab_handle: str = ""


@dataclass
class RedactionMap:
    """Map from pseudonym → StudentIdentity for rehydration."""

    by_pseudonym: dict = field(default_factory=dict)
    by_student_id: dict = field(default_factory=dict)

    def pseudonym_for(self, student: StudentIdentity) -> str:
        if student.student_id in self.by_student_id:
            return self.by_student_id[student.student_id]
        pseudonym = f"Student-{chr(ord('A') + len(self.by_pseudonym))}"
        self.by_pseudonym[pseudonym] = student
        self.by_student_id[student.student_id] = pseudonym
        return pseudonym


# ── redaction ──────────────────────────────────────────────────────────
# Used to split multi-token names so we can redact "de Boer", "Jan de Boer",
# "J. de Boer", "J de Boer", and just "de Boer" equivalently.
_NAME_SPLIT = re.compile(r"[ \-]")


def _name_variants(display_name: str, first_name: str = "") -> List[str]:
    """
    Derive a list of name substrings to redact. Longest-first to avoid
    partial replacement (so "Jan de Boer" is swapped before "Jan").
    """
    variants = set()
    if display_name.strip():
        variants.add(display_name.strip())
        # Last name alone (everything after the first token)
        parts = _NAME_SPLIT.split(display_name.strip())
        if len(parts) > 1:
            variants.add(" ".join(parts[1:]))
        # First name alone
        if parts:
            variants.add(parts[0])
    if first_name.strip() and first_name.strip() not in variants:
        variants.add(first_name.strip())
    # Longest-first so "Jan de Boer" wins over "Jan"
    return sorted((v for v in variants if len(v) >= 2), key=len, reverse=True)


def _handle_variants(student: StudentIdentity) -> List[str]:
    """GitHub / GitLab handles to redact. Case-sensitive; GitHub handles are
    case-insensitive in URLs, so we match either casing."""
    return [h for h in (student.github_handle, student.gitlab_handle) if h]


def redact_for_llm(
    text: str,
    students: Iterable[StudentIdentity],
    redaction_map: RedactionMap | None = None,
) -> tuple[str, RedactionMap]:
    """
    Replace every occurrence of each student's identity (name, first name,
    email, GitHub/GitLab handle) with a stable pseudonym.

    Returns (redacted_text, redaction_map). Pass the same map back to
    rehydrate_from_llm() to reverse.

    Edge cases:
      - Case-insensitive matching on handles and emails.
      - Whole-word boundary for names (avoid clobbering "Jan" inside
        "Janssen").
      - Regex metacharacters in names are escaped.
    """
    if redaction_map is None:
        redaction_map = RedactionMap()

    out = text
    # Collect all replacements first so we can do them longest-first,
    # regardless of which student they belong to. Otherwise "Jan" might be
    # redacted for student A before "Jan de Boer" for student B.
    replacements: list[tuple[str, str, bool]] = []  # (pattern, replacement, case_insensitive)
    for student in students:
        pseudonym = redaction_map.pseudonym_for(student)
        # Emails: case-insensitive, exact.
        if student.email:
            replacements.append((re.escape(student.email), pseudonym, True))
        # Handles: case-insensitive, word-boundary so github.com/handle/repo
        # still matches but "handleSomethingElse" doesn't.
        for handle in _handle_variants(student):
            replacements.append((rf"\b{re.escape(handle)}\b", pseudonym, True))
        # Names: case-sensitive, whole-word.
        for name in _name_variants(student.display_name, student.first_name):
            # Whole-word: bounded by start/end or non-word chars.
            replacements.append((rf"(?<![\w]){re.escape(name)}(?![\w])", pseudonym, False))

    # Sort by pattern length desc so longer matches win.
    replacements.sort(key=lambda r: len(r[0]), reverse=True)

    for pattern, replacement, case_insensitive in replacements:
        flags = re.IGNORECASE if case_insensitive else 0
        out = re.sub(pattern, replacement, out, flags=flags)

    return out, redaction_map


def rehydrate_from_llm(
    text: str,
    redaction_map: RedactionMap,
) -> tuple[str, list[str]]:
    """
    Replace pseudonyms back to the student's display name.

    Returns (rehydrated_text, warnings). Warnings are populated if the LLM
    appears to have dropped a pseudonym (paraphrased "Student-A's function"
    → "the student's function"). That's a signal the comment should be
    flagged for docent attention.

    Regression test target: "LLM dropped the placeholder" detection per
    eng-review finding #10.
    """
    warnings: list[str] = []
    out = text

    # Check for paraphrase leakage: phrases like "the student" without a
    # corresponding pseudonym suggest the LLM forgot who it was talking about.
    if redaction_map.by_pseudonym:
        # Simple heuristic: if text mentions a generic "the student" but no
        # pseudonym, warn. Tune against the eval set.
        has_any_pseudonym = any(p in out for p in redaction_map.by_pseudonym)
        mentions_generic_student = bool(
            re.search(r"\bthe student\b|\bde student\b|\bde leerling\b", out, re.IGNORECASE)
        )
        if mentions_generic_student and not has_any_pseudonym:
            warnings.append(
                "LLM output mentions 'the student' without a pseudonym; "
                "possible paraphrase leakage. Flag for docent review."
            )

    # Replace pseudonyms in descending length order (Student-AA before Student-A
    # for future-proofing past 26 students).
    for pseudonym in sorted(redaction_map.by_pseudonym.keys(), key=len, reverse=True):
        student = redaction_map.by_pseudonym[pseudonym]
        # Prefer first_name for friendlier feedback ("Jan, try X")
        # Fall back to display_name when first_name missing.
        friendly = student.first_name or student.display_name or pseudonym
        out = out.replace(pseudonym, friendly)

    return out, warnings
