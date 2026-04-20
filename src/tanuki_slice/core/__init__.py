"""Core chunking primitives: client, models, scraper, chunker."""

from tanuki_slice.core.chunker import GitLabMRChunker, chunk_threads
from tanuki_slice.core.client import GitLabAPIError, GitLabClient
from tanuki_slice.core.models import Chunk, MRMetadata, Note, Thread
from tanuki_slice.core.scraper import scrape_mr

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
