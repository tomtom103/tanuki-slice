"""Tests for data models."""

from __future__ import annotations

from tanuki_slice.models import Chunk, MRMetadata, Note, Thread, estimate_tokens


def _mr() -> MRMetadata:
    return MRMetadata(
        project_id=1,
        mr_iid=2,
        title="t",
        description="d",
        source_branch="feat",
        target_branch="main",
        author="alice",
        web_url="https://gitlab.com/x/-/merge_requests/2",
    )


def _note(body: str = "hello world", author: str = "bob") -> Note:
    return Note(id=1, author=author, body=body, created_at="2026-01-01T00:00:00Z")


def test_estimate_tokens_floor_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("a") == 1
    assert estimate_tokens("abcd" * 10) == 10


def test_note_tokens_computed_post_init() -> None:
    note = _note("abcd" * 8)
    assert note.tokens == 8


def test_thread_tokens_sum_note_tokens() -> None:
    t = Thread(
        discussion_id="d1",
        file_path="a.py",
        line=1,
        notes=[_note("abcd" * 4), _note("abcd" * 6)],
    )
    assert t.tokens == 10


def test_thread_sort_key_orders_by_file_then_discussion_id() -> None:
    a = Thread(discussion_id="z", file_path="a.py", line=1, notes=[_note()])
    b = Thread(discussion_id="a", file_path="b.py", line=1, notes=[_note()])
    c = Thread(discussion_id="m", file_path="a.py", line=1, notes=[_note()])
    ordered = sorted([a, b, c], key=lambda t: t.sort_key)
    assert [t.discussion_id for t in ordered] == ["m", "z", "a"]


def test_chunk_to_dict_shape() -> None:
    t = Thread(
        discussion_id="d1",
        file_path="a.py",
        line=3,
        notes=[_note("body", "alice")],
        resolved=False,
    )
    chunk = Chunk(chunk_index=0, total_chunks=1, mr_metadata=_mr(), file_groups={"a.py": [t]})
    out = chunk.to_dict()
    assert out["chunk_id"] == "1/1"
    assert out["mr_metadata"]["mr_iid"] == 2
    assert out["files"][0]["path"] == "a.py"
    assert out["files"][0]["threads"][0]["discussion_id"] == "d1"
    assert out["files"][0]["threads"][0]["notes"][0]["author"] == "alice"
    assert "diff_hunk" not in out["files"][0]["threads"][0]
    assert out["stats"]["thread_count"] == 1
