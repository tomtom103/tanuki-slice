"""Tests for fingerprint-marker dedup."""

from __future__ import annotations

from tanuki_slice.review.dedup import (
    MARKER_REGEX,
    extract_markers,
    filter_new,
    render_marker,
)
from tanuki_slice.review.findings import Finding


def _finding(title: str = "t") -> Finding:
    return Finding(
        file_path="a.py",
        line=1,
        severity="warning",
        title=title,
        body="b",
        focus="correctness",
    )


def test_render_marker_shape() -> None:
    m = render_marker("abc123abc123")
    assert m == "<!-- tanuki:abc123abc123 -->"


def test_extract_markers_from_body() -> None:
    body = "inline note\n<!-- tanuki:deadbeef1234 -->\ntrailing"
    assert extract_markers(body) == {"deadbeef1234"}


def test_extract_markers_multiple() -> None:
    body = "<!-- tanuki:aaaaaaaaaaaa --> <!-- tanuki:bbbbbbbbbbbb -->"
    assert extract_markers(body) == {"a" * 12, "b" * 12}


def test_marker_regex_ignores_unknown_format() -> None:
    assert not MARKER_REGEX.search("<!-- tanuki:xyz -->")


def test_filter_new_splits_posted_vs_skipped() -> None:
    f1 = _finding(title="a")
    f2 = _finding(title="b")
    existing = {f1.fingerprint}
    to_post, skipped = filter_new([f1, f2], existing)
    assert to_post == [f2]
    assert skipped == [f1]
