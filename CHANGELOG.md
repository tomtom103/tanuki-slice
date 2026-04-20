# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/tomtom103/tanuki-slice/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tomtom103/tanuki-slice/releases/tag/v0.1.0
