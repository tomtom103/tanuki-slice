"""Tests for the GitLab client (offline bits)."""

from __future__ import annotations

from tanuki_slice.client import GitLabClient


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
