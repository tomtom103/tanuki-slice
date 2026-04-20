"""Tests for prompt rendering of diffs."""

from __future__ import annotations

from tanuki_slice.review.diff import (
    DiffHunk,
    DiffLine,
    FileDiff,
    MRDiff,
    render_for_prompt,
)


def _file() -> FileDiff:
    return FileDiff(
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
                    DiffLine(kind="context", old_line=10, new_line=10, text="def f():"),
                    DiffLine(kind="deleted", old_line=11, new_line=None, text="    return 1"),
                    DiffLine(kind="added", old_line=None, new_line=11, text="    return 2"),
                ],
            ),
        ],
    )


def test_render_includes_file_header_and_line_annotations() -> None:
    mr = MRDiff(base_sha="b", start_sha="s", head_sha="h", files=[_file()])
    out = render_for_prompt(mr)
    assert "### a.py" in out
    assert "[10] def f():" in out
    assert "- [-- ]     return 1" in out
    assert "+ [11]     return 2" in out


def test_render_marks_new_and_deleted_files() -> None:
    new_file = FileDiff(
        old_path="",
        new_path="b.py",
        new_file=True,
        deleted_file=False,
        renamed_file=False,
        hunks=[],
    )
    mr = MRDiff(base_sha="b", start_sha="s", head_sha="h", files=[new_file])
    assert "(new file)" in render_for_prompt(mr)
