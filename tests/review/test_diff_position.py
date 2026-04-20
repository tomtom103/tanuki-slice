"""Tests for position_for: mapping new_path:new_line to a DiffPosition."""

from __future__ import annotations

from tanuki_slice.review.diff import (
    DiffHunk,
    DiffLine,
    FileDiff,
    MRDiff,
    position_for,
)


def _mr() -> MRDiff:
    file_diff = FileDiff(
        old_path="a.py",
        new_path="a.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
        hunks=[
            DiffHunk(
                old_start=10,
                new_start=10,
                lines=[
                    DiffLine(kind="context", old_line=10, new_line=10, text="x"),
                    DiffLine(kind="added", old_line=None, new_line=11, text="y"),
                    DiffLine(kind="deleted", old_line=11, new_line=None, text="z"),
                    DiffLine(kind="context", old_line=12, new_line=12, text="w"),
                ],
            ),
        ],
    )
    return MRDiff(base_sha="b", start_sha="s", head_sha="h", files=[file_diff])


def test_position_on_added_line() -> None:
    pos = position_for(_mr(), "a.py", 11)
    assert pos is not None
    assert pos.new_line == 11
    assert pos.old_line is None
    assert pos.new_path == "a.py"


def test_position_on_context_line() -> None:
    pos = position_for(_mr(), "a.py", 12)
    assert pos is not None
    assert pos.new_line == 12


def test_position_on_untouched_line_returns_none() -> None:
    assert position_for(_mr(), "a.py", 999) is None


def test_position_on_unknown_file_returns_none() -> None:
    assert position_for(_mr(), "other.py", 11) is None
