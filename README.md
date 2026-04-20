# tanuki-slice

Chunk GitLab merge request discussion threads into deterministic, budget-aware batches for LLM and agentic workflows.

Reviewing a 400-comment MR with an LLM blows past every context window. `tanuki-slice` scrapes the MR's discussions via the GitLab API, groups comments and replies by file, and splits them into token-budgeted chunks that preserve file locality and thread context — so each chunk fits your model and can be processed in isolation.

## Features

- Stdlib-only HTTP client (no `requests` / `httpx` dependency).
- Greedy bin-packing that keeps same-file threads together.
- Oversized threads get their own chunk instead of being silently dropped.
- Resolved threads filtered out by default; opt in with `--include-resolved`.
- Deterministic ordering (file path, then discussion id) for stable diffs between runs.
- Strict typing, `py.typed` shipped for downstream consumers.

## Installation

```bash
uv sync
```

Or from PyPI once published:

```bash
pip install tanuki-slice
```

## Usage

### `chunk` — split MR discussions

```bash
# Set your GitLab token
export GITLAB_TOKEN="glpat-xxx"

# Chunk an MR's discussions into JSON
tanuki-slice chunk --project-id 123 --mr-iid 45

# Custom token budget and output file
tanuki-slice chunk --project-id 123 --mr-iid 45 --budget 8000 -o chunks.json

# Quick summary view
tanuki-slice chunk --project-id 123 --mr-iid 45 --summary

# Include resolved threads
tanuki-slice chunk --project-id 123 --mr-iid 45 --include-resolved

# Self-hosted GitLab
tanuki-slice chunk --project-id 123 --mr-iid 45 --gitlab-url https://gitlab.example.com
```

### `review` — LLM code review

```bash
# Required env
export GITLAB_TOKEN="glpat-xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"

# Review a MR (post inline + summary comments)
tanuki-slice review --project-id 123 --mr-iid 45

# Dry-run: print findings only
tanuki-slice review --project-id 123 --mr-iid 45 --dry-run

# Multi-focus + raise cap
tanuki-slice review --project-id 123 --mr-iid 45 --focus security --focus style --max-findings 20

# CI-friendly: skip confirm
tanuki-slice review --project-id 123 --mr-iid 45 --yes
```

Re-runs are safe: every posted comment embeds a fingerprint marker, and the next run reads existing notes to skip already-raised findings. Project-level defaults can be placed in a `tanuki.toml` file with a `[review]` table; CLI flags override it.

### Library

```python
from tanuki_slice import GitLabMRChunker

chunker = GitLabMRChunker(token="glpat-xxx")
chunks = chunker.scrape_and_chunk(project_id=123, mr_iid=45, token_budget=4000)

for chunk in chunks:
    print(chunk.to_dict())
```

## Output shape

Each chunk serializes to:

```json
{
  "chunk_id": "1/3",
  "mr_metadata": { "project_id": 123, "mr_iid": 45, "title": "...", "...": "..." },
  "files": [
    {
      "path": "src/foo.py",
      "threads": [
        {
          "discussion_id": "abc",
          "line": 42,
          "resolved": false,
          "notes": [{ "id": 1, "author": "alice", "body": "...", "created_at": "..." }]
        }
      ]
    }
  ],
  "stats": { "thread_count": 7, "estimated_tokens": 3820 }
}
```

Token counts are rough (`~4 chars/token`) — good enough for budgeting, not for billing.

## Configuration

| Environment Variable | Description | Default |
|---|---|---|
| `GITLAB_TOKEN` | Personal access token with `api` scope | *required* |
| `GITLAB_URL` | GitLab instance URL | `https://gitlab.com` |
| `ANTHROPIC_API_KEY` | Anthropic API key (required for `review`) | *required for review* |

`tanuki.toml` in the project root can set review defaults; keys under the `[review]` table map 1:1 to CLI flags (`focus`, `model`, `max_findings`, `max_diff_tokens`, `gitlab_url`).

## Status

The `chunk` and `review` commands are available. Future work: webhook daemon, multi-provider LLMs, and cross-chunk review for mega-MRs.

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/
```

## License

MIT — see [LICENSE](LICENSE).
