"""Tests for the GitLab client (offline bits)."""

from __future__ import annotations

from types import TracebackType
from unittest.mock import patch

from tanuki_slice.core.client import GitLabClient


def test_parse_next_link_returns_next_url() -> None:
    header = (
        '<https://gitlab.com/api/v4/projects/1?page=1>; rel="first", '
        '<https://gitlab.com/api/v4/projects/1?page=2>; rel="next", '
        '<https://gitlab.com/api/v4/projects/1?page=5>; rel="last"'
    )
    assert GitLabClient._parse_next_link(header) == "https://gitlab.com/api/v4/projects/1?page=2"


def test_parse_next_link_missing_returns_none() -> None:
    header = '<https://gitlab.com/api/v4/projects/1?page=1>; rel="first"'
    assert GitLabClient._parse_next_link(header) is None


def test_parse_next_link_empty_header() -> None:
    assert GitLabClient._parse_next_link("") is None


def test_base_url_trailing_slash_stripped() -> None:
    c = GitLabClient("https://gitlab.example.com/", "t")
    assert c.base_url == "https://gitlab.example.com"


def test_post_serializes_json_and_sets_headers() -> None:
    c = GitLabClient("https://gitlab.com", "tok")
    captured: dict[str, object] = {}

    class FakeResp:
        headers: dict[str, str] = {}

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id": 99}'

    def fake_urlopen(req: object, *a: object, **k: object) -> FakeResp:
        captured["url"] = req.full_url  # type: ignore[attr-defined]
        captured["method"] = req.get_method()  # type: ignore[attr-defined]
        captured["headers"] = dict(req.header_items())  # type: ignore[attr-defined]
        captured["body"] = req.data  # type: ignore[attr-defined]
        return FakeResp()

    with patch("tanuki_slice.core.client.urlopen", fake_urlopen):
        result = c.create_mr_note(1, 2, "hello")

    assert result == {"id": 99}
    assert captured["method"] == "POST"
    assert "/projects/1/merge_requests/2/notes" in str(captured["url"])
    hdrs = captured["headers"]
    assert isinstance(hdrs, dict)
    headers_lower = {k.lower(): v for k, v in hdrs.items()}
    assert headers_lower["private-token"] == "tok"
    assert headers_lower["content-type"] == "application/json"
    assert captured["body"] == b'{"body": "hello"}'
