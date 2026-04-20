"""Tests for unified-diff parsing."""

from __future__ import annotations

from tanuki_slice.review.diff import DiffLine, parse_unified_diff


def test_parses_single_hunk() -> None:
    raw = (
        "@@ -1,3 +1,4 @@\n"
        " line_a\n"
        "-removed\n"
        "+added1\n"
        "+added2\n"
        " line_b\n"
    )
    hunks = parse_unified_diff(raw)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.old_start == 1
    assert h.new_start == 1
    kinds = [ln.kind for ln in h.lines]
    assert kinds == ["context", "deleted", "added", "added", "context"]


def test_tracks_line_numbers() -> None:
    raw = (
        "@@ -10,2 +20,3 @@\n"
        " a\n"
        "+b\n"
        " c\n"
    )
    [h] = parse_unified_diff(raw)
    assert h.lines[0] == DiffLine(kind="context", old_line=10, new_line=20, text="a")
    assert h.lines[1] == DiffLine(kind="added", old_line=None, new_line=21, text="b")
    assert h.lines[2] == DiffLine(kind="context", old_line=11, new_line=22, text="c")


def test_multiple_hunks() -> None:
    raw = (
        "@@ -1,1 +1,1 @@\n"
        "-x\n"
        "+y\n"
        "@@ -10,1 +10,1 @@\n"
        "-p\n"
        "+q\n"
    )
    hunks = parse_unified_diff(raw)
    assert [h.old_start for h in hunks] == [1, 10]


def test_empty_diff_returns_no_hunks() -> None:
    assert parse_unified_diff("") == []


def test_handles_missing_count_shorthand() -> None:
    raw = "@@ -5 +7 @@\n x\n"
    [h] = parse_unified_diff(raw)
    assert h.old_start == 5
    assert h.new_start == 7
