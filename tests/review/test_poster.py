"""Tests for inline + summary body rendering."""

from __future__ import annotations

from tanuki_slice.review.diff import DiffPosition
from tanuki_slice.review.findings import Finding
from tanuki_slice.review.poster import render_inline_body, render_summary


def _finding(**overrides: object) -> Finding:
    base: dict[str, object] = {
        "file_path": "a.py",
        "line": 42,
        "severity": "warning",
        "title": "missing await",
        "body": "details",
        "focus": "correctness",
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


def test_render_inline_body_appends_marker() -> None:
    f = _finding()
    body = render_inline_body(f)
    assert body.startswith("**warning** missing await")
    assert "details" in body
    assert f"<!-- tanuki:{f.fingerprint} -->" in body


def test_render_summary_lists_findings_grouped() -> None:
    a = _finding(title="issue a", severity="blocker")
    b = _finding(title="issue b", line=10, severity="nit")
    out = render_summary([a, b])
    assert "Tanuki review" in out
    assert "1 blocker" in out
    assert "1 nit" in out
    assert "a.py:42" in out
    assert "a.py:10" in out
    assert f"<!-- tanuki:{a.fingerprint} -->" in out
    assert f"<!-- tanuki:{b.fingerprint} -->" in out


def test_gitlab_position_payload_has_required_keys() -> None:
    pos = DiffPosition(
        base_sha="b",
        start_sha="s",
        head_sha="h",
        old_path="a.py",
        new_path="a.py",
        new_line=3,
        old_line=None,
    )
    payload = pos.as_gitlab_payload()
    for k in ("base_sha", "start_sha", "head_sha", "new_path", "new_line", "position_type"):
        assert k in payload
