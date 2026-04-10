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
CHUNK_SIZE = 60    # lines per chunk
CHUNK_OVERLAP = 10 # overlap to preserve context across boundaries
TOP_K = 5          # number of similar chunks to return

_model: Optional["SentenceTransformer"] = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _chunk_code(path: str, content: str) -> list[dict]:
    """Split a file into overlapping chunks of CHUNK_SIZE lines."""
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

    @property
    def is_available(self) -> bool:
        return _FAISS_AVAILABLE

    @property
    def total_vectors(self) -> int:
        self._load()
        if self._index is None:
            return 0
        return self._index.ntotal
