"""Dedup via fingerprint markers embedded in posted comment bodies."""

from __future__ import annotations

import re
from typing import Any

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.review.findings import Finding

MARKER_REGEX = re.compile(r"<!--\s*tanuki:([0-9a-f]{12})\s*-->")


def render_marker(fingerprint: str) -> str:
    return f"<!-- tanuki:{fingerprint} -->"


def extract_markers(body: str) -> set[str]:
    return set(MARKER_REGEX.findall(body))


def fetch_existing_markers(
    client: GitLabClient, project_id: int, mr_iid: int
) -> set[str]:
    markers: set[str] = set()
    notes: list[dict[str, Any]] = client.get_mr_notes(project_id, mr_iid)
    for note in notes:
        body = note.get("body") or ""
        markers.update(extract_markers(body))
    discussions = client.get_mr_discussions(project_id, mr_iid)
    for disc in discussions:
        for note in disc.get("notes") or []:
            body = note.get("body") or ""
            markers.update(extract_markers(body))
    return markers


def filter_new(
    findings: list[Finding], existing_markers: set[str]
) -> tuple[list[Finding], list[Finding]]:
    to_post: list[Finding] = []
    skipped: list[Finding] = []
    for f in findings:
        if f.fingerprint in existing_markers:
            skipped.append(f)
        else:
            to_post.append(f)
    return to_post, skipped
