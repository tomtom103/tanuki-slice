"""Tests for the findings JSON parser."""

from __future__ import annotations

import pytest

from tanuki_slice.review.findings import Finding
from tanuki_slice.review.llm import parse_findings_response


def test_parses_valid_json_array() -> None:
    raw = (
        '[{"file": "a.py", "line": 3, "severity": "warning", '
        '"title": "t", "body": "b"}]'
    )
    findings = parse_findings_response(raw, focus="correctness")
    assert findings == [
        Finding(
            file_path="a.py",
            line=3,
            severity="warning",
            title="t",
            body="b",
            focus="correctness",
        )
    ]


def test_strips_code_fence_if_model_adds_one() -> None:
    raw = "```json\n[]\n```"
    assert parse_findings_response(raw, focus="correctness") == []


def test_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="invalid"):
        parse_findings_response("not json", focus="correctness")


def test_drops_items_with_missing_required_fields() -> None:
    raw = '[{"file": "a.py", "line": 1, "severity": "warning", "title": "t"}]'
    assert parse_findings_response(raw, focus="correctness") == []


def test_drops_items_with_invalid_severity() -> None:
    raw = (
        '[{"file": "a.py", "line": 1, "severity": "critical", '
        '"title": "t", "body": "b"}]'
    )
    assert parse_findings_response(raw, focus="correctness") == []
