"""Tests for Finding fingerprint behavior."""

from __future__ import annotations

from tanuki_slice.review.findings import Finding


def _f(**overrides: object) -> Finding:
    base: dict[str, object] = {
        "file_path": "a.py",
        "line": 10,
        "severity": "warning",
        "title": "missing await",
        "body": "the call must be awaited",
        "focus": "correctness",
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


def test_fingerprint_is_stable() -> None:
    assert _f().fingerprint == _f().fingerprint


def test_fingerprint_differs_when_line_changes() -> None:
    assert _f().fingerprint != _f(line=11).fingerprint


def test_fingerprint_differs_when_focus_changes() -> None:
    assert _f().fingerprint != _f(focus="security").fingerprint


def test_fingerprint_differs_when_title_changes() -> None:
    assert _f().fingerprint != _f(title="other").fingerprint


def test_fingerprint_is_12_hex_chars() -> None:
    fp = _f().fingerprint
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)
