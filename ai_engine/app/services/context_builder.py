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
    "php": [
        # matches: use App\Services\UserService;
        # matches: use App\Services\UserService as SomeAlias;
        # matches: use function App\helper;
        # matches: use const App\SOME_CONSTANT;
        re.compile(
            r"^\s*use\s+(?:function\s+|const\s+)?([\w\\]+)(?:\s+as\s+\w+)?\s*;",
            re.MULTILINE,
        ),
    ],
}

# File extensions to skip when reading context (binary / generated)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".min.js", ".min.css",
    ".lock", ".bin", ".pyc",
}

MAX_CONTEXT_FILES = 8   # G2: increased to accommodate transitive imports
MAX_FILE_BYTES = 8_000  # truncate large related files
MAX_TRANSITIVE_DEPTH = 2  # G2: follow imports 1 level deep (direct + 1 transitive)


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
        # Lazily-initialized PHP PSR-4 / PSR-0 resolver. Only loaded on first
        # PHP import encountered, then reused across files in this build().
        self._composer_resolver = None

    # ── Public API ──────────────────────────────────────────────────────────

    async def build(self, changed_files: list[dict]) -> list[dict]:
        """
        Given a list of changed file dicts (with "path", "language", "diff"),
        return a list of related file contents to inject as context.
        G2: follows transitive imports up to MAX_TRANSITIVE_DEPTH levels.
        G9: includes sibling files for brand-new files with no imports.
        """
        related: set[str] = set()
        changed_paths = {f["path"] for f in changed_files}

        # Direct imports from changed files
        for f in changed_files:
            imports = self._extract_imports(f.get("diff", ""), f.get("language", ""))
            resolved = self._resolve_paths(f["path"], imports)
            related.update(resolved)

            # G9: For new files with no resolved imports, add sibling files
            if not resolved and f.get("diff", "").startswith("new file"):
                siblings = self._find_sibling_files(f["path"])
                related.update(siblings[:3])

        # G2: Transitive imports — follow imports of imported files (1 extra level)
        if len(related) < MAX_CONTEXT_FILES:
            transitive: set[str] = set()
            for path in list(related)[:5]:  # limit transitive search to first 5
                content = await self._read_file(path)
                if content:
                    lang = self._detect_language(path)
                    imports = self._extract_imports_from_content(content, lang)
                    transitive.update(self._resolve_paths(path, imports))
            related.update(transitive)

        # Remove changed files from context
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

        # PHP namespaces contain backslashes — route them through ComposerResolver
        php_imports = [imp for imp in imports if "\\" in imp]
        if php_imports:
            resolved.extend(self._resolve_php_imports(php_imports))

        for imp in imports:
            if "\\" in imp:
                continue  # already handled by PHP branch
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

    # ── PHP: Composer PSR-4 / PSR-0 resolution ─────────────────────────────

    def _resolve_php_imports(self, namespaces: list[str]) -> list[str]:
        """
        Resolve PHP fully-qualified namespaces to repo-relative file paths via
        composer.json autoload. Returns only paths that exist in the repo HEAD.
        """
        # Lazy-init the resolver. Cheap when there's no composer.json.
        if self._composer_resolver is None:
            from .composer_resolver import ComposerResolver
            self._composer_resolver = ComposerResolver(self.repo_path)
            self._composer_resolver.load()

        resolver = self._composer_resolver
        resolved: list[str] = []
        for ns in namespaces:
            # Resolver returns an absolute path (filesystem). Convert to
            # repo-relative for the git-backed existence check / reads.
            abs_path = resolver.resolve(ns)
            if abs_path is None:
                continue
            try:
                rel = abs_path.resolve().relative_to(self.repo_path.resolve())
            except ValueError:
                continue
            rel_str = str(rel).replace("\\", "/")
            if self._file_exists_in_repo(rel_str):
                resolved.append(rel_str)
        return resolved

    # ── G2: Transitive import helpers ──────────────────────────────────────

    def _extract_imports_from_content(self, content: str, language: str) -> list[str]:
        """Extract import module names from full file content (not just diff)."""
        patterns = LANGUAGE_IMPORT_PATTERNS.get(language, [])
        matches: set[str] = set()
        for pattern in patterns:
            for m in pattern.finditer(content):
                matches.add(m.group(1))
        return list(matches)

    def _detect_language(self, path: str) -> str:
        """Detect language from file extension."""
        ext_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.tsx': 'typescript', '.jsx': 'javascript', '.vue': 'vue',
            '.java': 'java', '.go': 'go', '.rs': 'rust',
            '.php': 'php',
        }
        ext = Path(path).suffix.lower()
        return ext_map.get(ext, '')

    # ── G9: Sibling file context for new files ─────────────────────────────

    def _find_sibling_files(self, path: str) -> list[str]:
        """Find files in the same directory as `path` for context on new files."""
        parent = str(Path(path).parent)
        try:
            result = subprocess.run(
                ["git", "ls-tree", "--name-only", f"HEAD:{parent}"],
                cwd=self.repo_path,
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                return []
            siblings = []
            for name in result.stdout.strip().splitlines():
                full = f"{parent}/{name}" if parent != "." else name
                if full != path and not any(full.endswith(ext) for ext in SKIP_EXTENSIONS):
                    siblings.append(full)
            return siblings
        except Exception:
            return []

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
