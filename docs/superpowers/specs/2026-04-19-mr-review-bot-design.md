# Self-Reviewing MR Bot — MVP Design

**Status:** Design approved, ready to implement
**Date:** 2026-04-19
**Scope:** First MVP of `tanuki-slice review` subcommand.

## Goal

Add a `tanuki-slice review` CLI command that reviews a GitLab merge request with Claude and posts inline + summary comments back to the MR. CLI-only, stateless, safe-by-default.

## Decisions (from brainstorming)

| Dimension | Decision |
|---|---|
| Interface | CLI only. No daemon, no webhook. Runs ad-hoc or from CI. |
| LLM backend | Anthropic (Claude) via official SDK. No provider abstraction. |
| Output shape | Inline diff comments **and** a single summary comment on the MR. |
| Dedup | Stateless. Fingerprint markers (`<!-- tanuki:xxxx -->`) embedded in every posted comment; re-runs parse existing notes and skip fingerprint matches. GitLab is the source of truth. |
| Review focus | `--focus` flag: `correctness` (default), `security`, `style`, or `all`. |
| Context to LLM | Include existing unresolved discussions (reuse existing chunker) so the bot doesn't restate human reviewers. |
| Safety | Post-by-default. `--max-findings N` (default 10) caps output. Interactive confirm before posting; `--yes` skips for CI. `--dry-run` always available. |
| Config | CLI flags + optional `tanuki.toml` project file. Secrets via env only (`GITLAB_TOKEN`, `ANTHROPIC_API_KEY`). |
| Oversized diffs | Fail fast with a clear error if estimated tokens exceed the configured threshold. No multi-chunk review in MVP. |

## Package Layout

```
src/tanuki_slice/
├── core/                    # shared infra (used by chunk + review)
│   ├── client.py            # GitLabClient + GitLabAPIError
│   ├── models.py            # Note, Thread, MRMetadata, Chunk
│   ├── scraper.py
│   ├── chunker.py
│   └── tokens.py            # estimate_tokens
├── review/
│   ├── config.py
│   ├── diff.py              # fetch, parse, render, position mapping
│   ├── prompts.py           # focus-specific prompt templates
│   ├── llm.py               # Anthropic wrapper, structured output parser
│   ├── findings.py          # Finding dataclass + fingerprint
│   ├── dedup.py             # read existing notes, extract markers
│   ├── poster.py            # post inline + summary w/ safety rails
│   └── orchestrator.py      # glue: fetch → prompt → call → dedup → post
└── cli.py                   # Typer app w/ `chunk` and `review` subcommands
```

The existing `chunk` command keeps its behavior; imports shift to `core/`. A top-level re-export in `tanuki_slice/__init__.py` keeps the library API backward compatible.

**New runtime deps:** `anthropic` (LLM SDK). `tomllib` is stdlib (py3.11+).

## Data Model

```python
# review/findings.py
@dataclass(frozen=True)
class Finding:
    file_path: str          # new_path from diff
    line: int               # line in new file
    severity: Literal["blocker", "warning", "nit"]
    title: str              # short, one-liner, shown in summary
    body: str               # markdown review comment body
    focus: str              # "correctness" | "security" | "style"

    @property
    def fingerprint(self) -> str:
        raw = f"{self.file_path}|{self.line}|{self.focus}|{self.title}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
```

```python
# review/diff.py
@dataclass(frozen=True)
class DiffLine:
    kind: Literal["context", "added", "deleted"]
    old_line: int | None
    new_line: int | None
    text: str

@dataclass(frozen=True)
class DiffHunk:
    old_start: int
    new_start: int
    lines: list[DiffLine]

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
    files: list[FileDiff]

    @property
    def estimated_tokens(self) -> int: ...

@dataclass(frozen=True)
class DiffPosition:
    base_sha: str
    start_sha: str
    head_sha: str
    old_path: str | None
    new_path: str
    new_line: int
    old_line: int | None
    position_type: str = "text"
```

```python
# review/config.py
@dataclass
class ReviewConfig:
    project_id: int
    mr_iid: int
    focus: list[str]                  # ["correctness"] default; "all" expands to all three
    model: str                        # default "claude-sonnet-4-6"
    max_findings: int                 # default 10
    max_diff_tokens: int              # default 150_000
    dry_run: bool                     # default False
    yes: bool                         # skip confirm
    gitlab_url: str
    gitlab_token: str
    anthropic_api_key: str

    @classmethod
    def load(cls, cli_args: dict, toml_path: Path | None) -> "ReviewConfig":
        """Precedence: flags > env > TOML > defaults. Validate required fields."""
```

```python
# review/orchestrator.py
@dataclass
class ReviewResult:
    findings: list[Finding]           # after dedup
    skipped_dedup: list[Finding]
    demoted_to_summary: list[Finding] # inline position couldn't be built
    posted_inline: int
    posted_summary: bool
    dry_run: bool
```

## Diff Fetch and Position Mapping

**`GitLabClient.get_mr_diffs`** (new method on core client): `GET /projects/:id/merge_requests/:iid/diffs` with pagination.

**`fetch_mr_diff(client, project_id, mr_iid) -> MRDiff`**: calls `get_mr` for `diff_refs`, then `get_mr_diffs` for files, runs `parse_unified_diff` on each file's `diff` string.

**`parse_unified_diff(raw: str) -> list[DiffHunk]`**: pure parser. Handles `@@ -a,b +c,d @@` headers; tracks `old_line`/`new_line` counters per hunk; tags each line as `context`, `added`, or `deleted`.

**`render_for_prompt(diff: MRDiff) -> str`**: compact unified format with explicit `[new_line]` annotations so the model produces citable line numbers:

```
### src/foo.py  (modified)
@@ -10,4 +10,6 @@
  [10] def login(user):
- [-- ]     token = make_token(user)
+ [10]     token = make_token(user, scope="read")
+ [11]     audit_log.write(token)
  [12]     return token
```

**`position_for(diff, new_path, new_line) -> DiffPosition | None`**: looks up the file and line. Returns position if the line is `added` or `context` within a hunk (commentable); returns `None` otherwise — caller demotes to summary.

## Prompt and LLM Call

**`review/prompts.py`** holds one template per focus (`correctness.md`, `security.md`, `style.md`) plus a shared system prompt. Templates receive:

- MR metadata (title, description)
- Existing unresolved discussions (rendered via the existing chunker — typically one chunk)
- The annotated diff (via `render_for_prompt`)
- Explicit JSON output schema for findings

The model is asked to return **only** a JSON array of findings:

```json
[
  {
    "file": "src/foo.py",
    "line": 11,
    "severity": "warning",
    "title": "Audit log write isn't awaited",
    "body": "`audit_log.write(token)` returns a coroutine; without `await` the call is discarded. ..."
  }
]
```

**`review/llm.py`** wraps `anthropic.Anthropic().messages.create`. It:

1. Loads prompt templates via `prompts`.
2. Sends one LLM call **per focus** in the config.
3. Parses the JSON response (strict: must be a JSON array; any non-array or non-parseable response raises).
4. Validates each item against the `Finding` schema; drops malformed items with a warning.
5. Tags each parsed finding with the current focus.
6. Returns `list[Finding]`.

No streaming, no tool use, no structured output beta features in MVP — plain system + user prompt, parse JSON from response text.

## Dedup

**`review/dedup.py`**:

- `fetch_existing_markers(client, project_id, mr_iid) -> set[str]`: pulls all MR notes (existing method), regex-extracts `tanuki:([0-9a-f]{12})`.
- `filter_new(findings, markers) -> tuple[list[Finding], list[Finding]]`: returns `(to_post, skipped)`.

## Posting

**`review/poster.py`**:

- `post_inline(client, finding, position) -> None`: `POST /projects/:id/merge_requests/:iid/discussions` with `body` (finding markdown + appended marker) and `position` fields.
- `post_summary(client, findings) -> None`: single `POST /projects/:id/merge_requests/:iid/notes` with a rendered summary: header, counts by severity, bulleted `**file:line** — title` list. Each bullet includes its finding's marker.
- `render_inline_body(finding) -> str`: body markdown + `\n\n<!-- tanuki:FPRINT -->`.
- `render_summary(findings) -> str`.

Every posted comment (inline and each summary bullet reference) gets a fingerprint marker so dedup works uniformly.

**Safety rails in poster:**
- If `len(to_post) > max_findings`: print count, ask user to confirm posting the first N, or abort.
- If `not yes and not dry_run`: interactive `y/N` prompt showing counts (inline / summary / demoted).
- If `dry_run`: print finding list to stdout, skip every POST.

## Orchestrator Flow

```
CLI → ReviewConfig.load
   ↓
core.GitLabClient
   ↓
review.diff.fetch_mr_diff  ──┐
core.scraper.scrape_mr       │
core.chunker.chunk_threads   │── gather context
                             │
review.diff.estimated_tokens │
 (fail fast if over threshold)
                             │
for each focus in config:    │
  review.llm.call(           │
    prompt(focus, metadata,
           discussions, diff))
 → findings                  │
                             │
merge + dedup locally by     │
 fingerprint                 │
                             │
review.dedup.fetch_existing_markers
review.dedup.filter_new
                             │
map each finding → position  │
 via review.diff.position_for│
 (None → demote to summary)  │
                             │
apply max_findings cap       │
confirm unless --yes         │
                             │
review.poster.post_inline (n×)
review.poster.post_summary (1×)
                             ↓
                      ReviewResult
```

## Error Handling

- `GitLabAPIError` (already exists): surfaced with clear CLI message.
- `AnthropicError`: caught, printed with model + status; exit 1.
- Malformed LLM JSON: bail with partial-findings warning, no posts. MVP does not attempt reprompt.
- Oversized diff: raise `DiffTooLarge(tokens, limit)`; CLI prints message with actual + limit and suggests smaller scope.
- Missing required config: raise in `ReviewConfig.load`, CLI exits with actionable text.

## CLI Surface

```
tanuki-slice chunk ...    # existing, unchanged behavior
tanuki-slice review --project-id X --mr-iid Y [options]

Options:
  --focus [correctness|security|style|all]   default: correctness
  --model TEXT                               default: claude-sonnet-4-6
  --max-findings INT                         default: 10
  --max-diff-tokens INT                      default: 150000
  --dry-run                                  default: false
  --yes                                      skip confirm prompt
  --gitlab-url TEXT                          override GITLAB_URL
  --config PATH                              override tanuki.toml path
  --output PATH                              also write findings JSON
```

Restructuring `chunk` from the current single-command layout into `tanuki-slice chunk` is part of this work.

## Config File Shape

`tanuki.toml` at repo root (loaded if present):

```toml
[review]
focus = ["correctness"]
model = "claude-sonnet-4-6"
max_findings = 10
max_diff_tokens = 150000
```

Flags override file; file overrides defaults. Secrets are never read from TOML.

## Testing Strategy

All pure functions get unit tests; all network-adjacent code gets tested against a fake client.

- **`diff.parse_unified_diff`**: multiple hunk shapes, added/deleted/context mixes, new files, deleted files, renames.
- **`diff.render_for_prompt`**: golden output on a small fixture.
- **`diff.position_for`**: added line → position; context line → position; deleted/untouched → None.
- **`findings.Finding.fingerprint`**: stable across reruns, different inputs → different fingerprints.
- **`dedup.fetch_existing_markers`**: extracts markers from mixed comment bodies.
- **`dedup.filter_new`**: correctly partitions findings.
- **`poster.render_inline_body` / `render_summary`**: golden snapshots including markers.
- **`config.ReviewConfig.load`**: precedence (flags > env > TOML > default), missing required fields raise.
- **`llm.parse_findings`**: valid JSON array → findings; malformed → warning + empty; extra fields ignored.
- **`orchestrator`**: integration test using fake client + fake LLM client, end-to-end flow with dry-run assertions.

CI target: `ruff`, `mypy --strict`, `pytest` — all green on every commit.

## Out of Scope (MVP)

- Webhook / daemon mode.
- Multi-provider LLM abstraction.
- Local dedup DB.
- Per-chunk review of oversized diffs.
- MR approval / label automation, pipeline-status gating.
- Re-review on new pushes (bot currently re-runs blind; user can manually re-invoke).
- Secret scrubbing in prompts (relies on GitLab permissions).

## Migration Notes

The top-level `tanuki_slice/__init__.py` keeps `GitLabMRChunker`, `Chunk`, `Note`, `Thread`, `MRMetadata`, and `chunk_threads` exported so downstream consumers of the library API are unaffected by the `core/` split.

The CLI entry point changes from single-command to multi-command; users invoking `tanuki-slice --project-id ...` must switch to `tanuki-slice chunk --project-id ...`. Release this as `0.2.0`. Document the change in `CHANGELOG.md` under **Changed** (BREAKING).
