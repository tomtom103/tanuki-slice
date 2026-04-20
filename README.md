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

### CLI

```bash
# Set your GitLab token
export GITLAB_TOKEN="glpat-xxx"

# Chunk an MR's discussions into JSON
tanuki-slice --project-id 123 --mr-iid 45

# Custom token budget and output file
tanuki-slice --project-id 123 --mr-iid 45 --budget 8000 -o chunks.json

# Quick summary view
tanuki-slice --project-id 123 --mr-iid 45 --summary

# Include resolved threads
tanuki-slice --project-id 123 --mr-iid 45 --include-resolved

# Self-hosted GitLab
tanuki-slice --project-id 123 --mr-iid 45 --gitlab-url https://gitlab.example.com
```

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

## Roadmap

`tanuki-slice` is evolving from a chunking library into a self-reviewing MR bot. The current `chunk` command handles ingestion; an upcoming `review` subcommand will close the loop by posting LLM-generated feedback directly to a merge request.

### Planned: `tanuki-slice review`

```bash
# Review a MR with Claude, post inline + summary comments
tanuki-slice review --project-id 123 --mr-iid 45

# Dry-run: print findings, don't post
tanuki-slice review --project-id 123 --mr-iid 45 --dry-run

# Focus on a specific aspect
tanuki-slice review --project-id 123 --mr-iid 45 --focus security

# Skip the confirm prompt (for CI)
tanuki-slice review --project-id 123 --mr-iid 45 --yes
```

**MVP scope (in design):**

| Feature | Decision |
|---|---|
| Interface | CLI only |
| LLM backend | Anthropic (Claude) |
| Output | Inline diff comments **and** summary comment on the MR |
| Dedup | Stateless — fingerprint markers embedded in comment bodies, re-reads existing notes on re-run |
| Focus | `--focus` flag: `correctness` (default), `security`, `style`, or `all` |
| Context | Includes existing unresolved discussions so the bot doesn't restate human reviewers |
| Safety | Post-by-default with `--max-findings` cap and confirm prompt; `--yes` to skip; `--dry-run` to preview |
| Config | CLI flags + optional `tanuki.toml` project file |
| Oversized diffs | Fail fast for MVP (no multi-pass chunking yet) |

**Required secrets:** `GITLAB_TOKEN` (unchanged) and `ANTHROPIC_API_KEY` for the review command.

**Package layout after split:**

```
src/tanuki_slice/
├── core/        # client, models, scraper, chunker (current code, regrouped)
└── review/      # new: diff fetch, prompts, LLM, findings, dedup, poster
```

The existing `chunk` command keeps its behavior; `review` is additive.

### Not in MVP (deferred)

- Webhook / daemon mode (CLI only for now — run from cron or CI).
- Multi-provider LLM abstraction (Anthropic-only until a second provider earns it).
- Local dedup DB (GitLab is the source of truth).
- Cross-chunk finding merging for mega-MRs (fail-fast first, chunk later).
- MR approval / label automation, pipeline-status gating.

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/
```

## License

MIT — see [LICENSE](LICENSE).
