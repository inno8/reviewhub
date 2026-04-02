"""
Phase 3 – Context-Aware Reviewer
Parses imports from changed files and retrieves related file contents from the
cached bare repo so the LLM understands cross-file dependencies.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Optional

LANGUAGE_IMPORT_PATTERNS: dict[str, list[re.Pattern]] = {
    "python": [
        re.compile(r"^\s*import\s+([\w\.]+)", re.MULTILINE),
        re.compile(r"^\s*from\s+([\w\.]+)\s+import", re.MULTILINE),
    ],
    "javascript": [
        re.compile(r"""(?:import|require)\s*\(?['"]([^'"]+)['"]\)?"""),
    ],
    "typescript": [
        re.compile(r"""(?:import|require)\s*\(?['"]([^'"]+)['"]\)?"""),
    ],
    "vue": [
        re.compile(r"""(?:import|require)\s*\(?['"]([^'"]+)['"]\)?"""),
    ],
    "java": [
        re.compile(r"^\s*import\s+([\w\.]+);", re.MULTILINE),
    ],
    "go": [
        re.compile(r'"([\w\.\/]+)"'),
    ],
    "rust": [
        re.compile(r"^\s*use\s+([\w:]+)", re.MULTILINE),
    ],
}

# File extensions to skip when reading context (binary / generated)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".min.js", ".min.css",
    ".lock", ".bin", ".pyc",
}

MAX_CONTEXT_FILES = 5
MAX_FILE_BYTES = 8_000  # truncate large related files


class ContextBuilder:
    """
    Builds context (related files + their contents) for a set of changed files.

    Usage:
        cb = ContextBuilder(repo_path)
        context = await cb.build(changed_files)
        # context = [{"path": "...", "content": "..."}, ...]
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    # ── Public API ──────────────────────────────────────────────────────────

    async def build(self, changed_files: list[dict]) -> list[dict]:
        """
        Given a list of changed file dicts (with "path", "language", "diff"),
        return a list of related file contents to inject as context.
        """
        related: set[str] = set()
        for f in changed_files:
            imports = self._extract_imports(f.get("diff", ""), f.get("language", ""))
            related.update(self._resolve_paths(f["path"], imports))

        # Remove files that are already being reviewed
        changed_paths = {f["path"] for f in changed_files}
        related -= changed_paths

        context: list[dict] = []
        for path in list(related)[:MAX_CONTEXT_FILES]:
            content = await self._read_file(path)
            if content is not None:
                context.append({"path": path, "content": content})

        return context

    # ── Import parsing ───────────────────────────────────────────────────────

    def _extract_imports(self, diff: str, language: str) -> list[str]:
        """Extract import module names from a diff."""
        patterns = LANGUAGE_IMPORT_PATTERNS.get(language, [])
        added_lines = "\n".join(
            l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")
        )
        matches: set[str] = set()
        for pattern in patterns:
            for m in pattern.finditer(added_lines):
                matches.add(m.group(1))
        return list(matches)

    def _resolve_paths(self, source_file: str, imports: list[str]) -> list[str]:
        """
        Convert import module names to probable repo file paths.
        Handles:
          - Python: from app.services.foo import bar → app/services/foo.py
          - JS/TS: ./utils/helpers → relative to source_file
          - Absolute / package imports are ignored (not in repo)
        """
        resolved: list[str] = []
        source_dir = Path(source_file).parent

        for imp in imports:
            # Relative JS/TS imports
            if imp.startswith("."):
                candidates = [
                    (source_dir / imp).with_suffix(ext)
                    for ext in (".ts", ".js", ".vue", ".tsx", ".jsx", ".py")
                ]
                candidates.append(source_dir / imp / "index.ts")
                candidates.append(source_dir / imp / "index.js")
                for c in candidates:
                    norm = str(c).replace("\\", "/").lstrip("/")
                    if self._file_exists_in_repo(norm):
                        resolved.append(norm)
                        break
            # Python dotted path
            elif "." in imp and not imp.startswith("http"):
                py_path = imp.replace(".", "/") + ".py"
                if self._file_exists_in_repo(py_path):
                    resolved.append(py_path)
        return resolved

    def _file_exists_in_repo(self, path: str) -> bool:
        """Check if a file exists in the bare/non-bare repo."""
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"HEAD:{path}"],
                cwd=self.repo_path,
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── File content retrieval ───────────────────────────────────────────────

    async def _read_file(self, path: str) -> Optional[str]:
        """Read file content from HEAD of the cached repo."""
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            return None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "show", f"HEAD:{path}"],
                cwd=self.repo_path,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                return None
            content = result.stdout
            if len(content) > MAX_FILE_BYTES:
                content = content[:MAX_FILE_BYTES] + "\n... [truncated] ..."
            return content
        except Exception:
            return None
