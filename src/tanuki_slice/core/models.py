"""Data models for GitLab MR discussion threads and chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tanuki_slice.core.tokens import estimate_tokens

__all__ = [
    "Chunk",
    "MRMetadata",
    "Note",
    "Thread",
    "estimate_tokens",
]


@dataclass
class Note:
    id: int
    author: str
    body: str
    created_at: str
    resolved: bool | None = None
    tokens: int = 0

    def __post_init__(self) -> None:
        self.tokens = estimate_tokens(self.body)


@dataclass
class Thread:
    """A discussion thread: one top-level comment + its replies."""

    discussion_id: str
    file_path: str | None
    line: int | None
    notes: list[Note] = field(default_factory=list)
    resolved: bool = False

    @property
    def tokens(self) -> int:
        return sum(n.tokens for n in self.notes)

    @property
    def sort_key(self) -> tuple[str, str]:
        """Stable sort key: file path then discussion id."""
        return (self.file_path or "", self.discussion_id)


@dataclass
class MRMetadata:
    project_id: int
    mr_iid: int
    title: str
    description: str
    source_branch: str
    target_branch: str
    author: str
    web_url: str

    @property
    def tokens(self) -> int:
        text = f"{self.title} {self.description} {self.source_branch} {self.target_branch}"
        return estimate_tokens(text) + 50


@dataclass
class Chunk:
    """A batch of threads sized to fit within a token budget."""

    chunk_index: int
    total_chunks: int
    mr_metadata: MRMetadata
    file_groups: dict[str, list[Thread]] = field(default_factory=dict)

    @property
    def thread_count(self) -> int:
        return sum(len(threads) for threads in self.file_groups.values())

    @property
    def tokens(self) -> int:
        return self.mr_metadata.tokens + sum(
            t.tokens for threads in self.file_groups.values() for t in threads
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": f"{self.chunk_index + 1}/{self.total_chunks}",
            "mr_metadata": {
                "project_id": self.mr_metadata.project_id,
                "mr_iid": self.mr_metadata.mr_iid,
                "title": self.mr_metadata.title,
                "description_snippet": self.mr_metadata.description[:500],
                "source_branch": self.mr_metadata.source_branch,
                "target_branch": self.mr_metadata.target_branch,
                "author": self.mr_metadata.author,
                "web_url": self.mr_metadata.web_url,
            },
            "files": [
                {
                    "path": file_path,
                    "threads": [
                        {
                            "discussion_id": t.discussion_id,
                            "line": t.line,
                            "resolved": t.resolved,
                            "notes": [
                                {
                                    "id": n.id,
                                    "author": n.author,
                                    "body": n.body,
                                    "created_at": n.created_at,
                                }
                                for n in t.notes
                            ],
                        }
                        for t in threads
                    ],
                }
                for file_path, threads in self.file_groups.items()
            ],
            "stats": {
                "thread_count": self.thread_count,
                "estimated_tokens": self.tokens,
            },
        }
