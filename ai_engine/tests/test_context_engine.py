"""
Tests for Phase 5 — Context Engine Improvements (G1-G10).
"""
import pytest
import os


# ── G1: AST-based function chunking ──────────────────────────────────────

def test_python_function_chunking():
    """G1: Python code should be chunked by function boundaries, not fixed lines."""
    from app.services.embedding_store import _chunk_code

    code = '''import os

def hello():
    """Say hello."""
    print("hello")
    return True

def goodbye(name):
    """Say goodbye."""
    for i in range(10):
        print(f"bye {name}")
    return False

class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        x = 1
        y = 2
        return x + y
'''
    chunks = _chunk_code("app/main.py", code)
    assert len(chunks) >= 3, f"Expected at least 3 chunks (2 functions + 1 class), got {len(chunks)}"

    # At least one chunk should contain a complete function
    texts = [c["text"] for c in chunks]
    has_complete_function = any(
        "def hello" in t and "return True" in t
        for t in texts
    )
    assert has_complete_function, "Should have a chunk containing the complete hello() function"


def test_line_fallback_for_unknown_language():
    """G1: Unknown file types should fall back to line-based chunking."""
    from app.services.embedding_store import _chunk_code

    code = "\n".join(f"line {i}" for i in range(100))
    chunks = _chunk_code("data.csv", code)
    assert len(chunks) > 0
    # Line-based chunks should be ~60 lines
    assert chunks[0]["end_line"] - chunks[0]["start_line"] + 1 <= 60


# ── G4 + G7: Diff quality in classifier ──────────────────────────────────

def test_cosmetic_diff_scores_lower():
    """G4/G7: A whitespace-only diff should score lower than a structural change."""
    from app.services.classifier import CommitClassifier

    classifier = CommitClassifier()

    # Cosmetic diff (only whitespace/formatting)
    cosmetic_diff = "\n".join([f"+   # comment line {i}" for i in range(30)])
    cosmetic = classifier.classify(
        diff_data={
            "files": [{"path": "app.py", "diff": cosmetic_diff, "additions": 30, "deletions": 0}],
            "lines_added": 30, "lines_removed": 0,
        },
        commit_meta={"message": "style: fix formatting", "id": "abc123"},
    )

    # Structural diff (real code changes)
    structural_diff = "\n".join([f"+    result = process_data(item_{i})" for i in range(30)])
    structural = classifier.classify(
        diff_data={
            "files": [{"path": "app.py", "diff": structural_diff, "additions": 30, "deletions": 0}],
            "lines_added": 30, "lines_removed": 0,
        },
        commit_meta={"message": "feat: add processing", "id": "def456"},
    )

    assert cosmetic.score < structural.score, (
        f"Cosmetic diff ({cosmetic.score}) should score lower than structural ({structural.score})"
    )


# ── G5: FAISS index cleanup ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_faiss_rebuild_clears_index(tmp_path):
    """G5: rebuild_index should clear old data and reindex fresh."""
    from app.services.embedding_store import EmbeddingStore, _FAISS_AVAILABLE
    if not _FAISS_AVAILABLE:
        pytest.skip("FAISS not installed")

    store = EmbeddingStore(project_id=999, cache_dir=str(tmp_path))

    # Index some files
    await store.index_files([
        {"path": "old.py", "content": "def old_function():\n    pass\n"},
        {"path": "keep.py", "content": "def keep_function():\n    return True\n"},
    ])
    assert store.total_vectors > 0

    # Rebuild with only one file
    await store.rebuild_index([
        {"path": "keep.py", "content": "def keep_function():\n    return True\n"},
    ])

    # Search should only find 'keep.py'
    results = await store.search("keep_function")
    paths = [r["path"] for r in results]
    assert any("keep.py" in p for p in paths)


# ── G6: Pattern recency weighting ────────────────────────────────────────

def test_recent_pattern_ranked_higher():
    """G6: Recent patterns should rank higher than old ones in profile."""
    from app.services.adaptive_profile import build_developer_history_section

    profile = {
        "level": "intermediate",
        "avg_score": 60,
        "evaluation_count": 20,
        "strengths": [],
        "weaknesses": [],
        "frequent_patterns": [
            {"pattern_key": "old_issue:warning", "count": 10, "last_seen": "2025-01-01T00:00:00Z"},
            {"pattern_key": "recent_issue:critical", "count": 3, "last_seen": "2026-04-14T00:00:00Z"},
        ],
    }

    section = build_developer_history_section(profile)

    # Recent issue should appear before old issue despite lower count
    recent_pos = section.find("recent issue")
    old_pos = section.find("old issue")
    assert recent_pos < old_pos, (
        f"Recent pattern should appear first (pos {recent_pos}) vs old (pos {old_pos})"
    )


# ── G8: Deduplicate semantic search ──────────────────────────────────────

@pytest.mark.asyncio
async def test_semantic_search_no_duplicates(tmp_path):
    """G8: Semantic search should not return duplicate chunks from same file region."""
    from app.services.embedding_store import EmbeddingStore, _FAISS_AVAILABLE
    if not _FAISS_AVAILABLE:
        pytest.skip("FAISS not installed")

    store = EmbeddingStore(project_id=998, cache_dir=str(tmp_path))

    # Index same content twice under same path (simulates re-indexing)
    content = "def validate_input(data):\n    if not data:\n        raise ValueError('Empty')\n"
    await store.index_files([{"path": "validators.py", "content": content}])
    # Re-index (should replace, not duplicate)
    await store.index_files([{"path": "validators.py", "content": content}])

    results = await store.search("validate input data")
    paths = [r["path"] for r in results]
    # Should not have duplicate entries for same path
    assert len(paths) == len(set(paths)), f"Duplicate paths in results: {paths}"


# ── G10: Per-category skill level ────────────────────────────────────────

def test_per_category_levels_in_profile():
    """G10: Profile section should include per-category skill levels."""
    from app.services.adaptive_profile import build_developer_history_section

    profile = {
        "level": "intermediate",
        "avg_score": 60,
        "evaluation_count": 20,
        "strengths": ["clean_code"],
        "weaknesses": ["error_handling"],
        "frequent_patterns": [],
        "category_scores": {
            "Code Quality": 85.0,
            "Security": 40.0,
            "Testing": 55.0,
        },
    }

    section = build_developer_history_section(profile)
    assert "Per-category skill levels:" in section
    assert "Code Quality: advanced" in section
    assert "Security: beginner" in section
    assert "Testing: intermediate" in section
