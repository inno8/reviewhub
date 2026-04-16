"""
Phase 4 – FAISS Embedding Store
Chunks code, generates embeddings with sentence-transformers, and stores /
searches per-project FAISS indexes.

Design decisions
- One FAISS index per project stored at {GIT_CACHE_DIR}/faiss/{project_id}.index
- Metadata (path, chunk_text) stored in a companion JSON file next to the index
- Embeddings are generated lazily – the model is loaded once and reused
- Graceful degradation: if faiss or sentence_transformers are not installed the
  module still loads but all public methods become no-ops returning empty results
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Optional heavy deps ──────────────────────────────────────────────────────
try:
    import faiss  # type: ignore
    import numpy as np  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False
    logger.warning(
        "faiss-cpu / sentence-transformers not installed. "
        "Phase 4 semantic context will be disabled. "
        "Run: pip install faiss-cpu sentence-transformers"
    )

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast, great for code
CHUNK_SIZE = 60    # fallback lines per chunk when AST parsing fails
CHUNK_OVERLAP = 10 # overlap to preserve context across boundaries
TOP_K = 5          # number of similar chunks to return
MAX_CHUNK_LINES = 120  # max lines per AST-based chunk

_model: Optional["SentenceTransformer"] = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _chunk_code(path: str, content: str) -> list[dict]:
    """
    G1: Split a file into chunks aligned to function/class boundaries when possible.
    Falls back to line-based chunking if AST parsing fails or is unavailable.
    """
    # Try AST-based chunking first
    ast_chunks = _chunk_by_ast(path, content)
    if ast_chunks:
        return ast_chunks

    # Fallback: line-based overlapping chunks
    return _chunk_by_lines(path, content)


def _chunk_by_ast(path: str, content: str) -> list[dict]:
    """
    G1: Parse code with tree-sitter to extract function/class/method boundaries.
    Returns chunks aligned to code structure, or empty list if parsing fails.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.rb'):
        return []

    try:
        # Use regex-based function detection as lightweight alternative to tree-sitter
        # (tree-sitter requires compiled grammars per language which may not be installed)
        lines = content.splitlines()
        boundaries = _detect_function_boundaries(lines, ext)

        if not boundaries:
            return []

        chunks = []
        for start, end, name in boundaries:
            chunk_lines = lines[start:end]
            if len(chunk_lines) > MAX_CHUNK_LINES:
                # Split oversized functions into sub-chunks
                for sub_chunks in _split_large_block(path, chunk_lines, start):
                    chunks.append(sub_chunks)
            else:
                chunks.append({
                    "path": path,
                    "start_line": start + 1,
                    "end_line": end,
                    "text": "\n".join(chunk_lines),
                    "symbol": name,
                })

        # Add any module-level code not inside a function/class
        if chunks:
            covered = set()
            for c in chunks:
                covered.update(range(c["start_line"] - 1, c["end_line"]))
            uncovered = [i for i in range(len(lines)) if i not in covered]
            if uncovered and len(uncovered) > 3:
                module_text = "\n".join(lines[i] for i in uncovered[:CHUNK_SIZE])
                chunks.insert(0, {
                    "path": path,
                    "start_line": 1,
                    "end_line": max(uncovered[:CHUNK_SIZE]) + 1,
                    "text": module_text,
                    "symbol": "<module>",
                })

        return chunks
    except Exception:
        return []


def _detect_function_boundaries(lines: list[str], ext: str) -> list[tuple[int, int, str]]:
    """
    Detect function/class/method start and end lines using indentation and patterns.
    Returns list of (start_line_idx, end_line_idx, name).
    """
    boundaries = []

    if ext == '.py':
        pattern = re.compile(r'^(class |def |async def )(\w+)')
    elif ext in ('.js', '.ts', '.jsx', '.tsx'):
        pattern = re.compile(
            r'^(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=|class\s+(\w+))'
        )
    elif ext == '.java':
        pattern = re.compile(
            r'^\s*(?:public|private|protected|static|\s)*\s+(?:class|interface|void|int|String|boolean|[\w<>\[\]]+)\s+(\w+)\s*[\({]'
        )
    elif ext == '.go':
        pattern = re.compile(r'^func\s+(?:\([\w\s*]+\)\s*)?(\w+)')
    elif ext == '.rs':
        pattern = re.compile(r'^(?:pub\s+)?(?:fn|struct|impl|enum|trait)\s+(\w+)')
    elif ext == '.rb':
        pattern = re.compile(r'^(?:\s*)(?:def|class|module)\s+(\w+)')
    else:
        return []

    i = 0
    while i < len(lines):
        line = lines[i]
        m = pattern.match(line)
        if m:
            name = next((g for g in m.groups() if g), "unknown")
            start = i

            if ext == '.py':
                # Python: use indentation to find end
                base_indent = len(line) - len(line.lstrip())
                end = i + 1
                while end < len(lines):
                    stripped = lines[end].strip()
                    if stripped == '' or stripped.startswith('#'):
                        end += 1
                        continue
                    current_indent = len(lines[end]) - len(lines[end].lstrip())
                    if current_indent <= base_indent and stripped:
                        break
                    end += 1
            elif ext in ('.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs'):
                # Brace-based: count { and } to find matching close
                end = _find_brace_end(lines, i)
            elif ext == '.rb':
                end = _find_ruby_end(lines, i)
            else:
                end = min(i + CHUNK_SIZE, len(lines))

            boundaries.append((start, end, name))
            i = end
        else:
            i += 1

    return boundaries


def _find_brace_end(lines: list[str], start: int) -> int:
    """Find the end of a brace-delimited block."""
    depth = 0
    found_first = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
                found_first = True
            elif ch == '}':
                depth -= 1
                if found_first and depth == 0:
                    return i + 1
    return min(start + CHUNK_SIZE, len(lines))


def _find_ruby_end(lines: list[str], start: int) -> int:
    """Find matching 'end' for a Ruby def/class/module."""
    depth = 0
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if re.match(r'^(def|class|module|if|unless|while|until|for|begin|do)\b', stripped):
            depth += 1
        if stripped == 'end':
            depth -= 1
            if depth == 0:
                return i + 1
    return min(start + CHUNK_SIZE, len(lines))


def _split_large_block(path: str, chunk_lines: list[str], offset: int) -> list[dict]:
    """Split an oversized function into smaller sub-chunks with overlap."""
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for i in range(0, len(chunk_lines), step):
        sub = chunk_lines[i:i + CHUNK_SIZE]
        chunks.append({
            "path": path,
            "start_line": offset + i + 1,
            "end_line": offset + i + len(sub),
            "text": "\n".join(sub),
        })
    return chunks


def _chunk_by_lines(path: str, content: str) -> list[dict]:
    """Fallback: split a file into overlapping chunks of CHUNK_SIZE lines."""
    lines = content.splitlines()
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for i in range(0, max(1, len(lines) - CHUNK_OVERLAP), step):
        chunk_lines = lines[i : i + CHUNK_SIZE]
        text = "\n".join(chunk_lines)
        chunks.append({
            "path": path,
            "start_line": i + 1,
            "end_line": i + len(chunk_lines),
            "text": text,
        })
    return chunks


class EmbeddingStore:
    """
    Per-project FAISS index for semantic code search.

    Usage:
        store = EmbeddingStore(project_id, cache_dir)
        await store.index_files([{"path": "...", "content": "..."}])
        results = await store.search("missing error handling", top_k=5)
    """

    def __init__(self, project_id: int, cache_dir: str):
        self.project_id = project_id
        self.base = Path(cache_dir) / "faiss" / str(project_id)
        self.index_path = self.base / "index.faiss"
        self.meta_path = self.base / "meta.json"
        self._index: Optional["faiss.Index"] = None
        self._meta: list[dict] = []

    # ── Public API ────────────────────────────────────────────────────────────

    async def index_files(self, files: list[dict]) -> None:
        """
        Add / update embeddings for a list of files.
        files = [{"path": "...", "content": "..."}]
        Existing entries for the same paths are replaced.
        """
        if not _FAISS_AVAILABLE or not files:
            return
        try:
            self._load()
            model = _get_model()
            new_chunks: list[dict] = []
            for f in files:
                # Remove old entries for this path
                self._meta = [m for m in self._meta if m["path"] != f["path"]]
                new_chunks.extend(_chunk_code(f["path"], f["content"]))

            if not new_chunks:
                return

            texts = [c["text"] for c in new_chunks]
            vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            vecs = vecs.astype("float32")

            if self._index is None:
                dim = vecs.shape[1]
                self._index = faiss.IndexFlatIP(dim)  # inner product = cosine on normalized vecs

            self._index.add(vecs)
            self._meta.extend(new_chunks)
            self._save()
            logger.info(
                "[FAISS] project=%s indexed %d chunks from %d files",
                self.project_id, len(new_chunks), len(files),
            )
        except Exception as exc:
            logger.warning("[FAISS] index_files failed: %s", exc)

    async def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """
        Semantic search over the project index.
        Returns list of {"path", "start_line", "end_line", "text", "score"}.
        """
        if not _FAISS_AVAILABLE:
            return []
        try:
            self._load()
            if self._index is None or self._index.ntotal == 0:
                return []
            model = _get_model()
            q_vec = model.encode([query], show_progress_bar=False, normalize_embeddings=True)
            q_vec = q_vec.astype("float32")
            k = min(top_k, self._index.ntotal)
            scores, indices = self._index.search(q_vec, k)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._meta):
                    continue
                entry = dict(self._meta[idx])
                entry["score"] = float(score)
                results.append(entry)
            return results
        except Exception as exc:
            logger.warning("[FAISS] search failed: %s", exc)
            return []

    async def search_by_diff(self, diff: str, top_k: int = TOP_K) -> list[dict]:
        """
        Search using the added lines of a diff as the query.
        Useful for finding similar code patterns to a changed file.
        """
        added = " ".join(
            l[1:].strip()
            for l in diff.splitlines()
            if l.startswith("+") and not l.startswith("+++")
        )
        query = added[:1_000] if added else diff[:1_000]
        return await self.search(query, top_k=top_k)

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._index is not None:
            return
        if not _FAISS_AVAILABLE:
            return
        self.base.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists() and self.meta_path.exists():
            try:
                self._index = faiss.read_index(str(self.index_path))
                with open(self.meta_path, encoding="utf-8") as fh:
                    self._meta = json.load(fh)
                logger.debug(
                    "[FAISS] project=%s loaded index (%d vectors)",
                    self.project_id, self._index.ntotal,
                )
            except Exception as exc:
                logger.warning("[FAISS] failed to load index, rebuilding: %s", exc)
                self._index = None
                self._meta = []

    def _save(self) -> None:
        if not _FAISS_AVAILABLE or self._index is None:
            return
        self.base.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as fh:
            json.dump(self._meta, fh)

    async def rebuild_index(self, files: list[dict]) -> None:
        """
        G5: Rebuild the entire index from scratch.
        Call after batch analysis or to clean up stale entries.
        """
        if not _FAISS_AVAILABLE:
            return
        # Clear existing index
        self._index = None
        self._meta = []
        if self.index_path.exists():
            self.index_path.unlink()
        if self.meta_path.exists():
            self.meta_path.unlink()
        # Re-index all files
        await self.index_files(files)
        logger.info("[FAISS] project=%s rebuilt index with %d files", self.project_id, len(files))

    async def cleanup_deleted_files(self, existing_paths: set[str]) -> int:
        """
        G5: Remove entries for files that no longer exist in the repo.
        Returns count of removed entries.
        """
        if not _FAISS_AVAILABLE:
            return 0
        self._load()
        if not self._meta:
            return 0

        before = len(self._meta)
        remaining = [m for m in self._meta if m["path"] in existing_paths]
        removed = before - len(remaining)

        if removed > 0:
            # Rebuild index with remaining entries only
            self._meta = remaining
            texts = [m["text"] for m in remaining]
            model = _get_model()
            vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            vecs = vecs.astype("float32")
            dim = vecs.shape[1]
            self._index = faiss.IndexFlatIP(dim)
            self._index.add(vecs)
            self._save()
            logger.info("[FAISS] project=%s cleaned up %d stale entries", self.project_id, removed)

        return removed

    @property
    def is_available(self) -> bool:
        return _FAISS_AVAILABLE

    @property
    def total_vectors(self) -> int:
        self._load()
        if self._index is None:
            return 0
        return self._index.ntotal
