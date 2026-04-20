"""Chunk GitLab merge request discussion threads for agentic workflows."""

from tanuki_slice.chunker import GitLabMRChunker, chunk_threads
from tanuki_slice.models import Chunk, MRMetadata, Note, Thread

__all__ = [
    "Chunk",
    "GitLabMRChunker",
    "MRMetadata",
    "Note",
    "Thread",
    "chunk_threads",
]
