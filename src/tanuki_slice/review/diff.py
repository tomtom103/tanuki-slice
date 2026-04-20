"""Diff data model, unified-diff parser, LLM prompt rendering, and position mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.core.tokens import estimate_tokens

LineKind = Literal["context", "added", "deleted"]

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class DiffLine:
    kind: LineKind
    old_line: int | None
    new_line: int | None
    text: str


@dataclass
class DiffHunk:
    old_start: int
    new_start: int
    lines: list[DiffLine] = field(default_factory=list)


@dataclass(frozen=True)
class FileDiff:
    old_path: str
    new_path: str
    new_file: bool
    deleted_file: bool
    renamed_file: bool
    hunks: list[DiffHunk]


@dataclass(frozen=True)
class MRDiff:
    base_sha: str
    start_sha: str
    head_sha: str
    files: list[FileDiff] = field(default_factory=list)

    @property
    def estimated_tokens(self) -> int:
        total = 0
        for f in self.files:
            for h in f.hunks:
                for ln in h.lines:
                    total += estimate_tokens(ln.text)
            total += estimate_tokens(f.new_path) + estimate_tokens(f.old_path)
        return total


@dataclass(frozen=True)
class DiffPosition:
    base_sha: str
    start_sha: str
    head_sha: str
    old_path: str | None
    new_path: str
    new_line: int | None
    old_line: int | None
    position_type: str = "text"

    def as_gitlab_payload(self) -> dict[str, Any]:
        return {
            "base_sha": self.base_sha,
            "start_sha": self.start_sha,
            "head_sha": self.head_sha,
            "position_type": self.position_type,
            "old_path": self.old_path,
            "new_path": self.new_path,
            "new_line": self.new_line,
            "old_line": self.old_line,
        }


def parse_unified_diff(raw: str) -> list[DiffHunk]:
    """Parse a unified-diff body (no file headers) into hunks."""
    hunks: list[DiffHunk] = []
    current_hunk: DiffHunk | None = None
    old_counter = 0
    new_counter = 0

    for raw_line in raw.splitlines():
        match = _HUNK_HEADER.match(raw_line)
        if match:
            old_counter = int(match.group(1))
            new_counter = int(match.group(3))
            current_hunk = DiffHunk(
                old_start=old_counter,
                new_start=new_counter,
                lines=[],
            )
            hunks.append(current_hunk)
            continue

        if current_hunk is None:
            continue

        if raw_line.startswith("+"):
            current_hunk.lines.append(
                DiffLine(kind="added", old_line=None, new_line=new_counter, text=raw_line[1:])
            )
            new_counter += 1
        elif raw_line.startswith("-"):
            current_hunk.lines.append(
                DiffLine(kind="deleted", old_line=old_counter, new_line=None, text=raw_line[1:])
            )
            old_counter += 1
        elif raw_line.startswith(" "):
            current_hunk.lines.append(
                DiffLine(
                    kind="context",
                    old_line=old_counter,
                    new_line=new_counter,
                    text=raw_line[1:],
                )
            )
            old_counter += 1
            new_counter += 1
        elif raw_line.startswith("\\"):
            continue

    return hunks


def fetch_mr_diff(client: GitLabClient, project_id: int, mr_iid: int) -> MRDiff:
    mr = client.get_mr(project_id, mr_iid)
    refs = mr.get("diff_refs") or {}
    base_sha = refs.get("base_sha") or ""
    start_sha = refs.get("start_sha") or base_sha
    head_sha = refs.get("head_sha") or ""
    raw_diffs = client.get_mr_diffs(project_id, mr_iid)

    files: list[FileDiff] = []
    for raw in raw_diffs:
        files.append(
            FileDiff(
                old_path=raw.get("old_path") or "",
                new_path=raw.get("new_path") or "",
                new_file=bool(raw.get("new_file")),
                deleted_file=bool(raw.get("deleted_file")),
                renamed_file=bool(raw.get("renamed_file")),
                hunks=parse_unified_diff(raw.get("diff") or ""),
            )
        )
    return MRDiff(base_sha=base_sha, start_sha=start_sha, head_sha=head_sha, files=files)
