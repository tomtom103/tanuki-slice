"""Scraper: GitLab API responses to data model."""

from __future__ import annotations

from typing import Any

from tanuki_slice.client import GitLabClient
from tanuki_slice.models import MRMetadata, Note, Thread


def scrape_mr(
    client: GitLabClient, project_id: int, mr_iid: int
) -> tuple[MRMetadata, list[Thread]]:
    """Fetch MR metadata and all discussion threads."""
    mr: dict[str, Any] = client.get_mr(project_id, mr_iid)
    metadata = MRMetadata(
        project_id=project_id,
        mr_iid=mr_iid,
        title=mr["title"],
        description=mr.get("description") or "",
        source_branch=mr["source_branch"],
        target_branch=mr["target_branch"],
        author=mr["author"]["username"],
        web_url=mr["web_url"],
    )

    raw_discussions: list[dict[str, Any]] = client.get_mr_discussions(project_id, mr_iid)
    threads: list[Thread] = []

    for disc in raw_discussions:
        notes_data = disc.get("notes", [])
        if not notes_data:
            continue

        first_note = notes_data[0]
        if first_note.get("system", False):
            continue

        position = first_note.get("position") or {}
        file_path: str | None = position.get("new_path") or position.get("old_path")
        line: int | None = position.get("new_line") or position.get("old_line")

        notes = [
            Note(
                id=n["id"],
                author=n["author"]["username"],
                body=n["body"],
                created_at=n["created_at"],
                resolved=n.get("resolved"),
            )
            for n in notes_data
            if not n.get("system", False)
        ]

        if not notes:
            continue

        resolved: bool
        if "resolved" in disc:
            resolved = disc.get("resolved", False)
        else:
            resolved = any(n.resolved for n in notes if n.resolved is not None)

        thread = Thread(
            discussion_id=disc["id"],
            file_path=file_path,
            line=line,
            notes=notes,
            resolved=resolved,
        )
        threads.append(thread)

    threads.sort(key=lambda t: t.sort_key)
    return metadata, threads
