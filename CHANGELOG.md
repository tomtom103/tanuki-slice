# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-04-19

### Added
- `tanuki-slice review` subcommand: reviews a GitLab MR with Anthropic Claude, posts inline diff comments and a summary note.
- `core/` subpackage that groups the GitLab client, models, scraper, and chunker used by both `chunk` and `review`.
- `review/` subpackage with diff fetch, unified-diff parser, prompt templates, LLM wrapper, fingerprint-based dedup, and poster.
- Support for `tanuki.toml` project config file with a `[review]` table; CLI flags override it.
- Fingerprint markers (`<!-- tanuki:xxxx -->`) embedded in every posted comment so re-runs are idempotent against GitLab state.

### Changed (BREAKING)
- CLI is now multi-command. Previous invocation `tanuki-slice --project-id X --mr-iid Y` must be updated to `tanuki-slice chunk --project-id X --mr-iid Y`.
- Internal modules moved from `tanuki_slice.{client,models,scraper,chunker}` to `tanuki_slice.core.{client,models,scraper,chunker}`. Top-level library imports (`from tanuki_slice import GitLabMRChunker, Chunk, Note, Thread, MRMetadata, chunk_threads`) continue to work unchanged.

## [0.1.0] - 2026-04-19

### Added
- GitLab REST API client using Python stdlib (no external HTTP dependency).
- MR discussion scraper that normalizes notes, positions, and resolved state.
- Greedy bin-packing chunker that preserves file locality within a token budget.
- Oversized-thread handling: threads larger than the budget get their own chunk.
- `tanuki-slice` CLI built on Typer with JSON output and `--summary` mode.
- Library entrypoint `GitLabMRChunker` and `chunk_threads` for programmatic use.
- `py.typed` marker for downstream type checkers.
- Pytest suite covering models, chunker, scraper, and client parsing.

[Unreleased]: https://github.com/tomtom103/tanuki-slice/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tomtom103/tanuki-slice/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tomtom103/tanuki-slice/releases/tag/v0.1.0
