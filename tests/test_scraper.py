"""Tests for the scraper (no network, fake client)."""

from __future__ import annotations

from typing import Any

from tanuki_slice.core.scraper import scrape_mr


class FakeClient:
    def __init__(self, mr: dict[str, Any], discussions: list[dict[str, Any]]) -> None:
        self._mr = mr
        self._discussions = discussions

    def get_mr(self, project_id: int, mr_iid: int) -> dict[str, Any]:
        return self._mr

    def get_mr_discussions(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        return self._discussions


def _mr_payload() -> dict[str, Any]:
    return {
        "title": "My MR",
        "description": "body",
        "source_branch": "feat",
        "target_branch": "main",
        "author": {"username": "alice"},
        "web_url": "https://x",
    }


def _note(
    note_id: int,
    body: str,
    system: bool = False,
    resolved: bool | None = None,
) -> dict[str, Any]:
    return {
        "id": note_id,
        "author": {"username": "bob"},
        "body": body,
        "created_at": "2026-01-01T00:00:00Z",
        "system": system,
        "resolved": resolved,
        "position": None,
    }


def test_scrape_maps_metadata_fields() -> None:
    client = FakeClient(_mr_payload(), [])
    meta, threads = scrape_mr(client, 1, 2)  # type: ignore[arg-type]
    assert meta.title == "My MR"
    assert meta.author == "alice"
    assert threads == []


def test_system_only_discussion_skipped() -> None:
    disc = {
        "id": "d1",
        "notes": [_note(1, "auto", system=True)],
    }
    client = FakeClient(_mr_payload(), [disc])
    _, threads = scrape_mr(client, 1, 2)  # type: ignore[arg-type]
    assert threads == []


def test_position_extracts_file_and_line() -> None:
    note = _note(1, "comment")
    note["position"] = {"new_path": "foo.py", "new_line": 42}
    disc = {"id": "d1", "notes": [note], "resolved": False}
    client = FakeClient(_mr_payload(), [disc])
    _, threads = scrape_mr(client, 1, 2)  # type: ignore[arg-type]
    assert threads[0].file_path == "foo.py"
    assert threads[0].line == 42


def test_resolved_inferred_from_notes_when_missing_on_discussion() -> None:
    disc = {
        "id": "d1",
        "notes": [_note(1, "a", resolved=True), _note(2, "b", resolved=True)],
    }
    client = FakeClient(_mr_payload(), [disc])
    _, threads = scrape_mr(client, 1, 2)  # type: ignore[arg-type]
    assert threads[0].resolved is True


def test_threads_sorted_by_file_then_id() -> None:
    notes_a = [_note(1, "a")]
    notes_b = [_note(2, "b")]
    notes_c = [_note(3, "c")]
    notes_a[0]["position"] = {"new_path": "b.py", "new_line": 1}
    notes_b[0]["position"] = {"new_path": "a.py", "new_line": 1}
    notes_c[0]["position"] = {"new_path": "a.py", "new_line": 1}
    discussions = [
        {"id": "zz", "notes": notes_a, "resolved": False},
        {"id": "mm", "notes": notes_b, "resolved": False},
        {"id": "aa", "notes": notes_c, "resolved": False},
    ]
    client = FakeClient(_mr_payload(), discussions)
    _, threads = scrape_mr(client, 1, 2)  # type: ignore[arg-type]
    assert [t.discussion_id for t in threads] == ["aa", "mm", "zz"]
