"""Chunker: split threads into budget-aware batches."""

from __future__ import annotations

import os

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.core.models import Chunk, MRMetadata, Thread
from tanuki_slice.core.scraper import scrape_mr


def chunk_threads(
    metadata: MRMetadata,
    threads: list[Thread],
    token_budget: int = 4000,
    *,
    include_resolved: bool = False,
) -> list[Chunk]:
    """
    Split threads into chunks that fit within a token budget.

    Strategy:
    1. Filter resolved threads (optional).
    2. Group by file path (preserves file locality).
    3. Greedy bin-pack: try to keep same-file threads together,
       but split across files when budget is hit.
    4. Oversized threads (single thread > budget) get their own chunk.
    """
    if not include_resolved:
        threads = [t for t in threads if not t.resolved]

    if not threads:
        return []

    file_order: list[str] = []
    by_file: dict[str, list[Thread]] = {}
    for t in threads:
        key = t.file_path or "__mr_level__"
        if key not in by_file:
            file_order.append(key)
            by_file[key] = []
        by_file[key].append(t)

    chunks: list[Chunk] = []
    current_groups: dict[str, list[Thread]] = {}
    current_tokens = 0

    def seal_chunk() -> None:
        nonlocal current_groups, current_tokens
        if current_groups:
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    total_chunks=0,
                    mr_metadata=metadata,
                    file_groups=current_groups,
                )
            )
            current_groups = {}
            current_tokens = 0

    for file_path in file_order:
        for thread in by_file[file_path]:
            thread_cost = thread.tokens

            if thread_cost > token_budget:
                seal_chunk()
                chunks.append(
                    Chunk(
                        chunk_index=len(chunks),
                        total_chunks=0,
                        mr_metadata=metadata,
                        file_groups={file_path: [thread]},
                    )
                )
                continue

            if current_tokens + thread_cost > token_budget:
                seal_chunk()

            if file_path not in current_groups:
                current_groups[file_path] = []
            current_groups[file_path].append(thread)
            current_tokens += thread_cost

    seal_chunk()

    for c in chunks:
        c.total_chunks = len(chunks)

    return chunks


class GitLabMRChunker:
    """High-level interface: scrape + chunk in one call."""

    def __init__(
        self,
        gitlab_url: str | None = None,
        token: str | None = None,
    ) -> None:
        self.gitlab_url = gitlab_url or os.environ.get("GITLAB_URL", "https://gitlab.com")
        self.token = token or os.environ.get("GITLAB_TOKEN", "")
        if not self.token:
            raise ValueError("GitLab token required. Set GITLAB_TOKEN or pass token=.")
        self.client = GitLabClient(self.gitlab_url, self.token)

    def scrape_and_chunk(
        self,
        project_id: int,
        mr_iid: int,
        token_budget: int = 4000,
        *,
        include_resolved: bool = False,
    ) -> list[Chunk]:
        metadata, threads = scrape_mr(self.client, project_id, mr_iid)
        return chunk_threads(metadata, threads, token_budget, include_resolved=include_resolved)

    def scrape_and_chunk_as_dicts(
        self,
        project_id: int,
        mr_iid: int,
        token_budget: int = 4000,
        *,
        include_resolved: bool = False,
    ) -> list[dict[str, object]]:
        chunks = self.scrape_and_chunk(
            project_id, mr_iid, token_budget, include_resolved=include_resolved
        )
        return [c.to_dict() for c in chunks]
