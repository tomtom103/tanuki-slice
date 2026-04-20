"""Tests for the chunker."""

from __future__ import annotations

from tanuki_slice.chunker import chunk_threads
from tanuki_slice.models import MRMetadata, Note, Thread


def _mr() -> MRMetadata:
    return MRMetadata(
        project_id=1,
        mr_iid=2,
        title="t",
        description="d",
        source_branch="feat",
        target_branch="main",
        author="alice",
        web_url="https://x",
    )


def _thread(disc_id: str, file_path: str | None, body_chars: int, resolved: bool = False) -> Thread:
    note = Note(id=1, author="bob", body="x" * body_chars, created_at="2026-01-01T00:00:00Z")
    return Thread(
        discussion_id=disc_id,
        file_path=file_path,
        line=1,
        notes=[note],
        resolved=resolved,
    )


def test_empty_threads_returns_no_chunks() -> None:
    assert chunk_threads(_mr(), []) == []


def test_resolved_filtered_by_default() -> None:
    threads = [_thread("d1", "a.py", 40, resolved=True)]
    assert chunk_threads(_mr(), threads) == []


def test_resolved_included_when_flag_set() -> None:
    threads = [_thread("d1", "a.py", 40, resolved=True)]
    chunks = chunk_threads(_mr(), threads, include_resolved=True)
    assert len(chunks) == 1


def test_budget_splits_across_chunks() -> None:
    # Each note body of 400 chars -> 100 tokens
    threads = [_thread(f"d{i}", "a.py", 400) for i in range(5)]
    chunks = chunk_threads(_mr(), threads, token_budget=250)
    assert len(chunks) >= 2
    for c in chunks:
        non_meta_tokens = sum(t.tokens for ts in c.file_groups.values() for t in ts)
        assert non_meta_tokens <= 250


def test_file_locality_preserved() -> None:
    threads = [
        _thread("d1", "a.py", 40),
        _thread("d2", "a.py", 40),
        _thread("d3", "b.py", 40),
    ]
    chunks = chunk_threads(_mr(), threads, token_budget=10_000)
    assert len(chunks) == 1
    paths = list(chunks[0].file_groups.keys())
    assert paths == ["a.py", "b.py"]


def test_oversized_thread_gets_own_chunk() -> None:
    threads = [
        _thread("small", "a.py", 40),
        _thread("huge", "b.py", 40_000),
        _thread("small2", "c.py", 40),
    ]
    chunks = chunk_threads(_mr(), threads, token_budget=500)
    huge_chunks = [
        c
        for c in chunks
        if any(t.discussion_id == "huge" for ts in c.file_groups.values() for t in ts)
    ]
    assert len(huge_chunks) == 1
    assert huge_chunks[0].thread_count == 1


def test_mr_level_threads_grouped_under_placeholder() -> None:
    threads = [_thread("d1", None, 40)]
    chunks = chunk_threads(_mr(), threads)
    assert "__mr_level__" in chunks[0].file_groups


def test_total_chunks_set_on_each() -> None:
    threads = [_thread(f"d{i}", "a.py", 400) for i in range(6)]
    chunks = chunk_threads(_mr(), threads, token_budget=200)
    total = len(chunks)
    assert all(c.total_chunks == total for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(total))
