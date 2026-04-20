"""Chunk GitLab merge request discussion threads for agentic workflows."""

from tanuki_slice.core import (
    Chunk,
    GitLabAPIError,
    GitLabClient,
    GitLabMRChunker,
    MRMetadata,
    Note,
    Thread,
    chunk_threads,
    scrape_mr,
)

__all__ = [
    "Chunk",
    "GitLabAPIError",
    "GitLabClient",
    "GitLabMRChunker",
    "MRMetadata",
    "Note",
    "Thread",
    "chunk_threads",
    "scrape_mr",
]
