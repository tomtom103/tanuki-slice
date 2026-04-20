# MR Review Bot MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tanuki-slice review` CLI subcommand that reviews a GitLab merge request with Claude and posts inline + summary comments back to the MR.

**Architecture:** Split existing code into `core/` (client, models, scraper, chunker). Add a new `review/` subpackage with a diff fetcher and parser, Anthropic-backed LLM call, fingerprint-based dedup, inline/summary poster, and an orchestrator. CLI becomes multi-command (`chunk` and `review`).

**Tech Stack:** Python 3.12, `typer` (CLI), `anthropic` (Claude SDK), stdlib `urllib`, `pytest`, `mypy --strict`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-04-19-mr-review-bot-design.md`

---

## File Structure

**Moved files (same content, new location):**
- `src/tanuki_slice/client.py` → `src/tanuki_slice/core/client.py`
- `src/tanuki_slice/models.py` → `src/tanuki_slice/core/models.py`
- `src/tanuki_slice/scraper.py` → `src/tanuki_slice/core/scraper.py`
- `src/tanuki_slice/chunker.py` → `src/tanuki_slice/core/chunker.py`

**Extracted:**
- `src/tanuki_slice/core/tokens.py` — pulls `estimate_tokens` out of `models.py`

**New files:**
- `src/tanuki_slice/core/__init__.py`
- `src/tanuki_slice/review/__init__.py`
- `src/tanuki_slice/review/config.py`
- `src/tanuki_slice/review/findings.py`
- `src/tanuki_slice/review/diff.py`
- `src/tanuki_slice/review/prompts.py`
- `src/tanuki_slice/review/llm.py`
- `src/tanuki_slice/review/dedup.py`
- `src/tanuki_slice/review/poster.py`
- `src/tanuki_slice/review/orchestrator.py`
- `tests/review/__init__.py`
- `tests/review/test_config.py`
- `tests/review/test_findings.py`
- `tests/review/test_diff_parse.py`
- `tests/review/test_diff_render.py`
- `tests/review/test_diff_position.py`
- `tests/review/test_dedup.py`
- `tests/review/test_llm.py`
- `tests/review/test_poster.py`
- `tests/review/test_orchestrator.py`

**Modified:**
- `src/tanuki_slice/__init__.py` — re-export from `core` for backward compat
- `src/tanuki_slice/cli.py` — multi-command Typer app
- `src/tanuki_slice/core/client.py` — add `get_mr_diffs`, `get_mr_notes`, `create_mr_note`, `create_mr_discussion`
- `pyproject.toml` — add `anthropic` dep, bump version to `0.2.0`
- `CHANGELOG.md` — add `0.2.0` entry with **Changed (BREAKING)** note
- `README.md` — flip Roadmap section to Usage

---

## Task 1: Restructure package — create `core/` subpackage

**Files:**
- Create: `src/tanuki_slice/core/__init__.py`
- Move: `client.py`, `models.py`, `scraper.py`, `chunker.py` → `src/tanuki_slice/core/`
- Modify: `src/tanuki_slice/__init__.py`
- Modify: `src/tanuki_slice/cli.py` (imports only)

- [ ] **Step 1: Create the subpackage dir and move files**

```bash
mkdir -p src/tanuki_slice/core
git mv src/tanuki_slice/client.py src/tanuki_slice/core/client.py
git mv src/tanuki_slice/models.py src/tanuki_slice/core/models.py
git mv src/tanuki_slice/scraper.py src/tanuki_slice/core/scraper.py
git mv src/tanuki_slice/chunker.py src/tanuki_slice/core/chunker.py
```

- [ ] **Step 2: Create `core/__init__.py`**

```python
"""Shared infrastructure: GitLab client, models, scraper, chunker."""

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
```

- [ ] **Step 3: Update intra-core imports**

In `core/chunker.py`, `core/scraper.py`: change `from tanuki_slice.client` → `from tanuki_slice.core.client`, same for `models`, etc.

Run: `grep -rn "from tanuki_slice\." src/tanuki_slice/core/` — every match must reference `tanuki_slice.core.*`.

- [ ] **Step 4: Update top-level `__init__.py` for backward compat**

```python
"""Chunk GitLab merge request discussion threads for agentic workflows."""

from tanuki_slice.core.chunker import GitLabMRChunker, chunk_threads
from tanuki_slice.core.models import Chunk, MRMetadata, Note, Thread

__all__ = [
    "Chunk",
    "GitLabMRChunker",
    "MRMetadata",
    "Note",
    "Thread",
    "chunk_threads",
]
```

- [ ] **Step 5: Update `cli.py` imports**

Change `from tanuki_slice.chunker import GitLabMRChunker` → `from tanuki_slice.core.chunker import GitLabMRChunker`. Change `from tanuki_slice.client import GitLabAPIError` → `from tanuki_slice.core.client import GitLabAPIError`.

- [ ] **Step 6: Update existing tests' imports**

In `tests/test_*.py`: every `from tanuki_slice.X import Y` where X is `client`, `models`, `scraper`, `chunker` → `from tanuki_slice.core.X`.

- [ ] **Step 7: Run full check**

```bash
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -q
```

Expected: all green. 22 tests still pass.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: move core modules into tanuki_slice.core subpackage"
```

---

## Task 2: Extract `estimate_tokens` into `core/tokens.py`

**Files:**
- Create: `src/tanuki_slice/core/tokens.py`
- Modify: `src/tanuki_slice/core/models.py`

- [ ] **Step 1: Create `core/tokens.py`**

```python
"""Lightweight token estimation helpers."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/code mixed content."""
    return max(1, len(text) // 4)
```

- [ ] **Step 2: Remove `estimate_tokens` from `models.py` and import from `tokens.py`**

In `src/tanuki_slice/core/models.py`, delete the `estimate_tokens` function body and replace with:

```python
from tanuki_slice.core.tokens import estimate_tokens
```

Keep it re-exported (it's part of `__all__`-adjacent surface). Tests import it from `tanuki_slice.core.models`, which still works via the re-export.

- [ ] **Step 3: Run checks**

```bash
uv run pytest -q
```

Expected: 22 passed.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: split estimate_tokens into core/tokens.py"
```

---

## Task 3: Restructure CLI into multi-command app (`chunk` subcommand)

**Files:**
- Modify: `src/tanuki_slice/cli.py`

- [ ] **Step 1: Rewrite `cli.py` as multi-command Typer app**

```python
"""CLI interface for tanuki-slice."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated
from urllib.error import URLError

import typer

from tanuki_slice.core.chunker import GitLabMRChunker
from tanuki_slice.core.client import GitLabAPIError

app = typer.Typer(
    name="tanuki-slice",
    help="Scrape and review GitLab merge requests for LLM workflows.",
    add_completion=False,
    no_args_is_help=True,
)


@app.command("chunk")
def chunk_cmd(
    project_id: Annotated[int, typer.Option("--project-id", help="GitLab project ID")],
    mr_iid: Annotated[int, typer.Option("--mr-iid", help="Merge request IID")],
    budget: Annotated[int, typer.Option("--budget", help="Token budget per chunk")] = 4000,
    include_resolved: Annotated[
        bool, typer.Option("--include-resolved", help="Include resolved discussions")
    ] = False,
    gitlab_url: Annotated[
        str | None, typer.Option("--gitlab-url", help="GitLab instance URL")
    ] = None,
    token: Annotated[
        str | None, typer.Option("--token", help="GitLab personal access token")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("-o", "--output", help="Output file")
    ] = None,
    summary: Annotated[
        bool, typer.Option("--summary", help="Print chunk summary instead of full JSON")
    ] = False,
) -> None:
    """Scrape and chunk a GitLab merge request's discussion threads."""
    try:
        chunker = GitLabMRChunker(gitlab_url=gitlab_url, token=token)
        chunks = chunker.scrape_and_chunk(
            project_id=project_id,
            mr_iid=mr_iid,
            token_budget=budget,
            include_resolved=include_resolved,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except GitLabAPIError as exc:
        typer.echo(f"GitLab API error {exc.status}: {exc.reason}", err=True)
        raise typer.Exit(code=1) from exc
    except URLError as exc:
        typer.echo(f"Network error: {exc.reason}", err=True)
        raise typer.Exit(code=1) from exc

    if summary:
        typer.echo(f"MR !{mr_iid} -> {len(chunks)} chunks (budget: {budget} tokens)\n")
        for c in chunks:
            files = list(c.file_groups.keys())
            typer.echo(
                f"  Chunk {c.chunk_index + 1}/{c.total_chunks}: "
                f"{c.thread_count} threads, ~{c.tokens} tokens"
            )
            for f in files:
                n = len(c.file_groups[f])
                typer.echo(f"    {f}: {n} thread{'s' if n != 1 else ''}")
        return

    dicts = [c.to_dict() for c in chunks]
    json_output = json.dumps(dicts, indent=2)

    if output:
        output.write_text(json_output)
        typer.echo(f"Wrote {len(chunks)} chunks to {output}")
    else:
        typer.echo(json_output)


if __name__ == "__main__":
    sys.exit(app())
```

- [ ] **Step 2: Verify CLI help shows subcommand**

```bash
uv run tanuki-slice --help
uv run tanuki-slice chunk --help
```

Expected: top-level help lists `chunk`; `chunk --help` shows the existing options.

- [ ] **Step 3: Run existing tests**

```bash
uv run pytest -q
```

Expected: 22 passed.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(cli): restructure as multi-command Typer app"
```

---

## Task 4: Add `anthropic` dependency and bump version

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dep and bump version**

```bash
uv add 'anthropic>=0.40.0'
```

Then edit `pyproject.toml` manually: change `version = "0.1.0"` → `version = "0.2.0"`.

- [ ] **Step 2: Verify lock + install**

```bash
uv sync
uv run python -c "import anthropic; print(anthropic.__version__)"
```

Expected: a version number prints.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add anthropic dep, bump to 0.2.0-dev"
```

---

## Task 5: `review/findings.py` — Finding dataclass + fingerprint

**Files:**
- Create: `src/tanuki_slice/review/__init__.py`
- Create: `src/tanuki_slice/review/findings.py`
- Create: `tests/review/__init__.py`
- Create: `tests/review/test_findings.py`

- [ ] **Step 1: Create empty `review/__init__.py` and `tests/review/__init__.py`**

Both files: empty content.

- [ ] **Step 2: Write the failing test**

`tests/review/test_findings.py`:

```python
from tanuki_slice.review.findings import Finding


def _f(**overrides: object) -> Finding:
    base: dict[str, object] = {
        "file_path": "a.py",
        "line": 10,
        "severity": "warning",
        "title": "missing await",
        "body": "the call must be awaited",
        "focus": "correctness",
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


def test_fingerprint_is_stable() -> None:
    assert _f().fingerprint == _f().fingerprint


def test_fingerprint_differs_when_line_changes() -> None:
    assert _f().fingerprint != _f(line=11).fingerprint


def test_fingerprint_differs_when_focus_changes() -> None:
    assert _f().fingerprint != _f(focus="security").fingerprint


def test_fingerprint_differs_when_title_changes() -> None:
    assert _f().fingerprint != _f(title="other").fingerprint


def test_fingerprint_is_12_hex_chars() -> None:
    fp = _f().fingerprint
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)
```

- [ ] **Step 3: Run test, confirm failure**

```bash
uv run pytest tests/review/test_findings.py -v
```

Expected: fails (`Finding` doesn't exist).

- [ ] **Step 4: Implement `findings.py`**

```python
"""Findings produced by the reviewer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

Severity = Literal["blocker", "warning", "nit"]


@dataclass(frozen=True)
class Finding:
    file_path: str
    line: int
    severity: Severity
    title: str
    body: str
    focus: str

    @property
    def fingerprint(self) -> str:
        raw = f"{self.file_path}|{self.line}|{self.focus}|{self.title}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/review/test_findings.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/tanuki_slice/review/__init__.py src/tanuki_slice/review/findings.py tests/review/
git commit -m "feat(review): add Finding dataclass with fingerprint"
```

---

## Task 6: `review/config.py` — ReviewConfig with flags/env/TOML precedence

**Files:**
- Create: `src/tanuki_slice/review/config.py`
- Create: `tests/review/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/review/test_config.py`:

```python
from pathlib import Path

import pytest

from tanuki_slice.review.config import ReviewConfig, expand_focus


def test_expand_focus_single() -> None:
    assert expand_focus(["correctness"]) == ["correctness"]


def test_expand_focus_all() -> None:
    assert expand_focus(["all"]) == ["correctness", "security", "style"]


def test_expand_focus_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown focus"):
        expand_focus(["bogus"])


def _env() -> dict[str, str]:
    return {
        "GITLAB_TOKEN": "glpat-test",
        "GITLAB_URL": "https://gitlab.com",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }


def test_load_uses_defaults(tmp_path: Path) -> None:
    cfg = ReviewConfig.load(
        cli={"project_id": 1, "mr_iid": 2},
        env=_env(),
        toml_path=None,
    )
    assert cfg.project_id == 1
    assert cfg.mr_iid == 2
    assert cfg.focus == ["correctness"]
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.max_findings == 10
    assert cfg.max_diff_tokens == 150_000
    assert cfg.dry_run is False


def test_load_reads_toml(tmp_path: Path) -> None:
    toml = tmp_path / "tanuki.toml"
    toml.write_text(
        "[review]\n"
        'focus = ["security"]\n'
        "max_findings = 5\n"
    )
    cfg = ReviewConfig.load(
        cli={"project_id": 1, "mr_iid": 2},
        env=_env(),
        toml_path=toml,
    )
    assert cfg.focus == ["security"]
    assert cfg.max_findings == 5


def test_cli_overrides_toml(tmp_path: Path) -> None:
    toml = tmp_path / "tanuki.toml"
    toml.write_text("[review]\nmax_findings = 5\n")
    cfg = ReviewConfig.load(
        cli={"project_id": 1, "mr_iid": 2, "max_findings": 20},
        env=_env(),
        toml_path=toml,
    )
    assert cfg.max_findings == 20


def test_load_requires_gitlab_token() -> None:
    env = _env()
    del env["GITLAB_TOKEN"]
    with pytest.raises(ValueError, match="GITLAB_TOKEN"):
        ReviewConfig.load(cli={"project_id": 1, "mr_iid": 2}, env=env, toml_path=None)


def test_load_requires_anthropic_key() -> None:
    env = _env()
    del env["ANTHROPIC_API_KEY"]
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        ReviewConfig.load(cli={"project_id": 1, "mr_iid": 2}, env=env, toml_path=None)
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/review/test_config.py -v
```

Expected: fails (module missing).

- [ ] **Step 3: Implement `config.py`**

```python
"""Review configuration: CLI flags + env + TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_FOCUSES = ("correctness", "security", "style")
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_FINDINGS = 10
DEFAULT_MAX_DIFF_TOKENS = 150_000
DEFAULT_GITLAB_URL = "https://gitlab.com"


def expand_focus(focus: list[str]) -> list[str]:
    if focus == ["all"]:
        return list(VALID_FOCUSES)
    for f in focus:
        if f not in VALID_FOCUSES:
            raise ValueError(f"unknown focus: {f!r} (valid: {VALID_FOCUSES + ('all',)})")
    return focus


@dataclass
class ReviewConfig:
    project_id: int
    mr_iid: int
    focus: list[str] = field(default_factory=lambda: ["correctness"])
    model: str = DEFAULT_MODEL
    max_findings: int = DEFAULT_MAX_FINDINGS
    max_diff_tokens: int = DEFAULT_MAX_DIFF_TOKENS
    dry_run: bool = False
    yes: bool = False
    gitlab_url: str = DEFAULT_GITLAB_URL
    gitlab_token: str = ""
    anthropic_api_key: str = ""

    @classmethod
    def load(
        cls,
        cli: dict[str, Any],
        env: dict[str, str],
        toml_path: Path | None,
    ) -> "ReviewConfig":
        if "project_id" not in cli or "mr_iid" not in cli:
            raise ValueError("project_id and mr_iid are required")

        toml_review: dict[str, Any] = {}
        if toml_path is not None and toml_path.exists():
            data = tomllib.loads(toml_path.read_text())
            toml_review = data.get("review", {}) or {}

        def pick(key: str, default: Any) -> Any:
            if key in cli and cli[key] is not None:
                return cli[key]
            if key in toml_review:
                return toml_review[key]
            return default

        gitlab_token = env.get("GITLAB_TOKEN", "")
        if not gitlab_token:
            raise ValueError("GITLAB_TOKEN must be set in the environment")

        anthropic_api_key = env.get("ANTHROPIC_API_KEY", "")
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in the environment")

        focus = expand_focus(list(pick("focus", ["correctness"])))

        return cls(
            project_id=cli["project_id"],
            mr_iid=cli["mr_iid"],
            focus=focus,
            model=str(pick("model", DEFAULT_MODEL)),
            max_findings=int(pick("max_findings", DEFAULT_MAX_FINDINGS)),
            max_diff_tokens=int(pick("max_diff_tokens", DEFAULT_MAX_DIFF_TOKENS)),
            dry_run=bool(pick("dry_run", False)),
            yes=bool(pick("yes", False)),
            gitlab_url=str(pick("gitlab_url", None) or env.get("GITLAB_URL", DEFAULT_GITLAB_URL)),
            gitlab_token=gitlab_token,
            anthropic_api_key=anthropic_api_key,
        )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/review/test_config.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/config.py tests/review/test_config.py
git commit -m "feat(review): add ReviewConfig with flags/env/TOML precedence"
```

---

## Task 7: Extend `GitLabClient` — diffs, notes, and write endpoints

**Files:**
- Modify: `src/tanuki_slice/core/client.py`
- Modify: `tests/test_client.py` (or new test file for post logic)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_client.py`:

```python
from unittest.mock import patch, MagicMock

from tanuki_slice.core.client import GitLabClient


def test_post_serializes_json_and_sets_headers() -> None:
    c = GitLabClient("https://gitlab.com", "tok")
    captured: dict[str, object] = {}

    class FakeResp:
        headers = {}

        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def read(self) -> bytes:
            return b'{"id": 99}'

    def fake_urlopen(req, *a: object, **k: object) -> FakeResp:  # type: ignore[no-untyped-def]
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data
        return FakeResp()

    with patch("tanuki_slice.core.client.urlopen", fake_urlopen):
        result = c.create_mr_note(1, 2, "hello")

    assert result == {"id": 99}
    assert captured["method"] == "POST"
    assert "/projects/1/merge_requests/2/notes" in str(captured["url"])
    headers_lower = {k.lower(): v for k, v in captured["headers"].items()}  # type: ignore[attr-defined]
    assert headers_lower["private-token"] == "tok"
    assert headers_lower["content-type"] == "application/json"
    assert captured["body"] == b'{"body": "hello"}'
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/test_client.py -v
```

Expected: `create_mr_note` doesn't exist yet.

- [ ] **Step 3: Extend `core/client.py` with diffs + note/discussion endpoints**

Add these imports at the top if missing:

```python
from urllib.parse import urlencode
```

Add a `_post` helper and the new methods. Full updated `core/client.py`:

```python
"""Minimal GitLab REST API client using only stdlib."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitLabAPIError(Exception):
    def __init__(self, status: int, reason: str, url: str) -> None:
        self.status = status
        self.reason = reason
        self.url = url
        super().__init__(f"GitLab API {status} {reason} for {url}")


class GitLabClient:
    def __init__(self, gitlab_url: str, token: str) -> None:
        self.base_url = gitlab_url.rstrip("/")
        self.token = token

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}/api/v4{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        results: list[Any] = []
        next_url: str | None = url
        while next_url:
            this_url = next_url
            req = Request(this_url, headers={"PRIVATE-TOKEN": self.token})
            try:
                with urlopen(req) as resp:  # noqa: S310
                    data = json.loads(resp.read().decode())
                    if not isinstance(data, list):
                        return data
                    results.extend(data)
                    link = resp.headers.get("Link", "")
                    next_url = self._parse_next_link(link)
            except HTTPError as exc:
                reason = self._extract_reason(exc)
                raise GitLabAPIError(exc.code, reason, this_url) from exc

        return results

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self.base_url}/api/v4{path}"
        payload = json.dumps(body).encode()
        req = Request(
            url,
            data=payload,
            method="POST",
            headers={
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(req) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except HTTPError as exc:
            reason = self._extract_reason(exc)
            raise GitLabAPIError(exc.code, reason, url) from exc

    @staticmethod
    def _extract_reason(exc: HTTPError) -> str:
        try:
            body = exc.read().decode()
            payload = json.loads(body)
            if isinstance(payload, dict):
                for key in ("message", "error", "error_description"):
                    value = payload.get(key)
                    if isinstance(value, str) and value:
                        return value
        except (OSError, ValueError, UnicodeDecodeError):
            pass
        return str(exc.reason) or "Unknown error"

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        for part in link_header.split(","):
            if 'rel="next"' in part:
                match = re.search(r"<(.+?)>", part)
                if match:
                    return match.group(1)
        return None

    # --- READ endpoints ---

    def get_mr(self, project_id: int, mr_iid: int) -> dict[str, Any]:
        pid = quote(str(project_id), safe="")
        result: dict[str, Any] = self._get(f"/projects/{pid}/merge_requests/{mr_iid}")
        return result

    def get_mr_discussions(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        pid = quote(str(project_id), safe="")
        result: list[dict[str, Any]] = self._get(
            f"/projects/{pid}/merge_requests/{mr_iid}/discussions",
            params={"per_page": "100"},
        )
        return result

    def get_mr_notes(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        pid = quote(str(project_id), safe="")
        result: list[dict[str, Any]] = self._get(
            f"/projects/{pid}/merge_requests/{mr_iid}/notes",
            params={"per_page": "100"},
        )
        return result

    def get_mr_diffs(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        pid = quote(str(project_id), safe="")
        result: list[dict[str, Any]] = self._get(
            f"/projects/{pid}/merge_requests/{mr_iid}/diffs",
            params={"per_page": "100"},
        )
        return result

    # --- WRITE endpoints ---

    def create_mr_note(self, project_id: int, mr_iid: int, body: str) -> dict[str, Any]:
        pid = quote(str(project_id), safe="")
        result: dict[str, Any] = self._post(
            f"/projects/{pid}/merge_requests/{mr_iid}/notes",
            {"body": body},
        )
        return result

    def create_mr_discussion(
        self,
        project_id: int,
        mr_iid: int,
        body: str,
        position: dict[str, Any],
    ) -> dict[str, Any]:
        pid = quote(str(project_id), safe="")
        result: dict[str, Any] = self._post(
            f"/projects/{pid}/merge_requests/{mr_iid}/discussions",
            {"body": body, "position": position},
        )
        return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ -v -k "client"
```

Expected: all client tests pass including the new one.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/core/client.py tests/test_client.py
git commit -m "feat(core): extend GitLabClient with diffs, notes, and write endpoints"
```

---

## Task 8: `review/diff.py` — data model and unified-diff parser

**Files:**
- Create: `src/tanuki_slice/review/diff.py`
- Create: `tests/review/test_diff_parse.py`

- [ ] **Step 1: Write failing tests for the parser**

`tests/review/test_diff_parse.py`:

```python
from tanuki_slice.review.diff import DiffLine, parse_unified_diff


def test_parses_single_hunk() -> None:
    raw = (
        "@@ -1,3 +1,4 @@\n"
        " line_a\n"
        "-removed\n"
        "+added1\n"
        "+added2\n"
        " line_b\n"
    )
    hunks = parse_unified_diff(raw)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.old_start == 1
    assert h.new_start == 1
    kinds = [ln.kind for ln in h.lines]
    assert kinds == ["context", "deleted", "added", "added", "context"]


def test_tracks_line_numbers() -> None:
    raw = (
        "@@ -10,2 +20,3 @@\n"
        " a\n"
        "+b\n"
        " c\n"
    )
    [h] = parse_unified_diff(raw)
    assert h.lines[0] == DiffLine(kind="context", old_line=10, new_line=20, text="a")
    assert h.lines[1] == DiffLine(kind="added", old_line=None, new_line=21, text="b")
    assert h.lines[2] == DiffLine(kind="context", old_line=11, new_line=22, text="c")


def test_multiple_hunks() -> None:
    raw = (
        "@@ -1,1 +1,1 @@\n"
        "-x\n"
        "+y\n"
        "@@ -10,1 +10,1 @@\n"
        "-p\n"
        "+q\n"
    )
    hunks = parse_unified_diff(raw)
    assert [h.old_start for h in hunks] == [1, 10]


def test_empty_diff_returns_no_hunks() -> None:
    assert parse_unified_diff("") == []


def test_handles_missing_count_shorthand() -> None:
    # "@@ -5 +7 @@" is valid shorthand for count=1
    raw = "@@ -5 +7 @@\n x\n"
    [h] = parse_unified_diff(raw)
    assert h.old_start == 5
    assert h.new_start == 7
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/review/test_diff_parse.py -v
```

Expected: module missing, all fail.

- [ ] **Step 3: Implement the model + parser**

`src/tanuki_slice/review/diff.py`:

```python
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
            # "\ No newline at end of file" — informational, skip
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
```

- [ ] **Step 4: Run parser tests**

```bash
uv run pytest tests/review/test_diff_parse.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/diff.py tests/review/test_diff_parse.py
git commit -m "feat(review): add diff model and unified-diff parser"
```

---

## Task 9: `review/diff.py` — render_for_prompt and position_for

**Files:**
- Modify: `src/tanuki_slice/review/diff.py`
- Create: `tests/review/test_diff_render.py`
- Create: `tests/review/test_diff_position.py`

- [ ] **Step 1: Write failing tests for render**

`tests/review/test_diff_render.py`:

```python
from tanuki_slice.review.diff import (
    DiffHunk,
    DiffLine,
    FileDiff,
    MRDiff,
    render_for_prompt,
)


def _file() -> FileDiff:
    return FileDiff(
        old_path="a.py",
        new_path="a.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
        hunks=[
            DiffHunk(
                old_start=10,
                new_start=10,
                lines=[
                    DiffLine(kind="context", old_line=10, new_line=10, text="def f():"),
                    DiffLine(kind="deleted", old_line=11, new_line=None, text="    return 1"),
                    DiffLine(kind="added", old_line=None, new_line=11, text="    return 2"),
                ],
            ),
        ],
    )


def test_render_includes_file_header_and_line_annotations() -> None:
    mr = MRDiff(base_sha="b", start_sha="s", head_sha="h", files=[_file()])
    out = render_for_prompt(mr)
    assert "### a.py" in out
    assert "[10] def f():" in out
    assert "- [-- ]     return 1" in out
    assert "+ [11]     return 2" in out


def test_render_marks_new_and_deleted_files() -> None:
    new_file = FileDiff(
        old_path="",
        new_path="b.py",
        new_file=True,
        deleted_file=False,
        renamed_file=False,
        hunks=[],
    )
    mr = MRDiff(base_sha="b", start_sha="s", head_sha="h", files=[new_file])
    assert "(new file)" in render_for_prompt(mr)
```

`tests/review/test_diff_position.py`:

```python
from tanuki_slice.review.diff import (
    DiffHunk,
    DiffLine,
    FileDiff,
    MRDiff,
    position_for,
)


def _mr() -> MRDiff:
    file_diff = FileDiff(
        old_path="a.py",
        new_path="a.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
        hunks=[
            DiffHunk(
                old_start=10,
                new_start=10,
                lines=[
                    DiffLine(kind="context", old_line=10, new_line=10, text="x"),
                    DiffLine(kind="added", old_line=None, new_line=11, text="y"),
                    DiffLine(kind="deleted", old_line=11, new_line=None, text="z"),
                    DiffLine(kind="context", old_line=12, new_line=12, text="w"),
                ],
            ),
        ],
    )
    return MRDiff(base_sha="b", start_sha="s", head_sha="h", files=[file_diff])


def test_position_on_added_line() -> None:
    pos = position_for(_mr(), "a.py", 11)
    assert pos is not None
    assert pos.new_line == 11
    assert pos.old_line is None
    assert pos.new_path == "a.py"


def test_position_on_context_line() -> None:
    pos = position_for(_mr(), "a.py", 12)
    assert pos is not None
    assert pos.new_line == 12


def test_position_on_untouched_line_returns_none() -> None:
    assert position_for(_mr(), "a.py", 999) is None


def test_position_on_unknown_file_returns_none() -> None:
    assert position_for(_mr(), "other.py", 11) is None
```

- [ ] **Step 2: Confirm failures**

```bash
uv run pytest tests/review/test_diff_render.py tests/review/test_diff_position.py -v
```

Expected: both fail.

- [ ] **Step 3: Append `render_for_prompt` and `position_for` to `diff.py`**

At the end of `src/tanuki_slice/review/diff.py`:

```python
def render_for_prompt(diff: MRDiff) -> str:
    """Compact unified format with explicit [new_line] annotations."""
    out: list[str] = []
    for f in diff.files:
        label_bits: list[str] = []
        if f.new_file:
            label_bits.append("new file")
        elif f.deleted_file:
            label_bits.append("deleted")
        elif f.renamed_file:
            label_bits.append(f"renamed from {f.old_path}")
        else:
            label_bits.append("modified")
        label = ", ".join(label_bits)
        out.append(f"### {f.new_path or f.old_path}  ({label})")
        for h in f.hunks:
            out.append(f"@@ -{h.old_start} +{h.new_start} @@")
            for ln in h.lines:
                tag = f"[{ln.new_line}]" if ln.new_line is not None else "[-- ]"
                prefix = {
                    "added": "+",
                    "deleted": "-",
                    "context": " ",
                }[ln.kind]
                out.append(f"{prefix} {tag} {ln.text}")
        out.append("")
    return "\n".join(out)


def position_for(diff: MRDiff, new_path: str, new_line: int) -> DiffPosition | None:
    """Build an inline-comment position for a finding at new_path:new_line, or None."""
    for f in diff.files:
        if f.new_path != new_path:
            continue
        for h in f.hunks:
            for ln in h.lines:
                if ln.kind == "deleted":
                    continue
                if ln.new_line == new_line:
                    return DiffPosition(
                        base_sha=diff.base_sha,
                        start_sha=diff.start_sha,
                        head_sha=diff.head_sha,
                        old_path=f.old_path or None,
                        new_path=f.new_path,
                        new_line=new_line,
                        old_line=ln.old_line,
                    )
    return None
```

- [ ] **Step 4: Run the new tests**

```bash
uv run pytest tests/review/ -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/diff.py tests/review/test_diff_render.py tests/review/test_diff_position.py
git commit -m "feat(review): add render_for_prompt and position_for"
```

---

## Task 10: `review/prompts.py` — templates per focus

**Files:**
- Create: `src/tanuki_slice/review/prompts.py`

- [ ] **Step 1: Implement prompts**

```python
"""Prompt templates for the review bot."""

from __future__ import annotations

SYSTEM_PROMPT = """You are a meticulous staff-level code reviewer.

You receive a GitLab merge request diff and produce structured review findings.

Rules:
- Only comment on lines that appear in the provided diff, cited by their [new_line] tag.
- Skip anything already covered by the existing unresolved discussions.
- Prefer concrete, actionable feedback ("this call is missing await and will drop the task") over vague observations ("consider reviewing").
- If the diff is clean, return an empty JSON array. Do not invent issues.
- Output ONLY a JSON array. No prose, no markdown fences, no commentary.

Each finding is an object with keys: file (string), line (integer), severity (one of "blocker", "warning", "nit"), title (short one-liner), body (markdown explanation).
"""

_FOCUS_GUIDANCE: dict[str, str] = {
    "correctness": (
        "Focus on correctness: logic bugs, off-by-one errors, error handling, "
        "race conditions, API misuse, missing awaits, incorrect assumptions."
    ),
    "security": (
        "Focus on security: injection, authz/authn flaws, secret leakage, unsafe "
        "deserialization, path traversal, SSRF, weak crypto, missing input validation."
    ),
    "style": (
        "Focus on style and readability: naming, dead code, duplicated logic, "
        "unclear abstractions, comments that lie, functions doing too much."
    ),
}


def build_user_prompt(
    focus: str,
    mr_title: str,
    mr_description: str,
    existing_discussions: str,
    annotated_diff: str,
) -> str:
    guidance = _FOCUS_GUIDANCE.get(focus, _FOCUS_GUIDANCE["correctness"])
    return f"""## Review focus
{guidance}

## Merge request
Title: {mr_title}
Description:
{mr_description or "(none)"}

## Existing unresolved discussions
{existing_discussions or "(none)"}

## Diff
Each line is tagged with its [new_line] number. Use that number in the `line` field of your findings.

{annotated_diff}

Return ONLY a JSON array of findings.
"""
```

- [ ] **Step 2: Run full test suite to ensure nothing regressed**

```bash
uv run pytest -q
```

Expected: still passing.

- [ ] **Step 3: Commit**

```bash
git add src/tanuki_slice/review/prompts.py
git commit -m "feat(review): add focus-specific prompt templates"
```

---

## Task 11: `review/llm.py` — Anthropic wrapper + JSON finding parser

**Files:**
- Create: `src/tanuki_slice/review/llm.py`
- Create: `tests/review/test_llm.py`

- [ ] **Step 1: Write failing tests for the parser**

`tests/review/test_llm.py`:

```python
import pytest

from tanuki_slice.review.findings import Finding
from tanuki_slice.review.llm import parse_findings_response


def test_parses_valid_json_array() -> None:
    raw = (
        '[{"file": "a.py", "line": 3, "severity": "warning", '
        '"title": "t", "body": "b"}]'
    )
    findings = parse_findings_response(raw, focus="correctness")
    assert findings == [
        Finding(
            file_path="a.py",
            line=3,
            severity="warning",
            title="t",
            body="b",
            focus="correctness",
        )
    ]


def test_strips_code_fence_if_model_adds_one() -> None:
    raw = "```json\n[]\n```"
    assert parse_findings_response(raw, focus="correctness") == []


def test_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="invalid"):
        parse_findings_response("not json", focus="correctness")


def test_drops_items_with_missing_required_fields() -> None:
    raw = '[{"file": "a.py", "line": 1, "severity": "warning", "title": "t"}]'
    # missing "body"
    assert parse_findings_response(raw, focus="correctness") == []


def test_drops_items_with_invalid_severity() -> None:
    raw = (
        '[{"file": "a.py", "line": 1, "severity": "critical", '
        '"title": "t", "body": "b"}]'
    )
    assert parse_findings_response(raw, focus="correctness") == []
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/review/test_llm.py -v
```

Expected: module missing.

- [ ] **Step 3: Implement `llm.py`**

```python
"""Anthropic Claude wrapper and findings JSON parser."""

from __future__ import annotations

import json
from typing import Any, Protocol

from anthropic import Anthropic

from tanuki_slice.review.findings import Finding
from tanuki_slice.review.prompts import SYSTEM_PROMPT, build_user_prompt

VALID_SEVERITIES = {"blocker", "warning", "nit"}
REQUIRED_FIELDS = ("file", "line", "severity", "title", "body")


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, model: str) -> str: ...


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def complete(self, *, system: str, user: str, model: str) -> str:
        resp = self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)


def parse_findings_response(raw: str, focus: str) -> list[Finding]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        data: Any = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON from model: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("invalid JSON: expected top-level array")

    findings: list[Finding] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if not all(key in item for key in REQUIRED_FIELDS):
            continue
        severity = item["severity"]
        if severity not in VALID_SEVERITIES:
            continue
        try:
            findings.append(
                Finding(
                    file_path=str(item["file"]),
                    line=int(item["line"]),
                    severity=severity,
                    title=str(item["title"]),
                    body=str(item["body"]),
                    focus=focus,
                )
            )
        except (TypeError, ValueError):
            continue
    return findings


def run_review(
    client: LLMClient,
    *,
    model: str,
    focus: str,
    mr_title: str,
    mr_description: str,
    existing_discussions: str,
    annotated_diff: str,
) -> list[Finding]:
    user = build_user_prompt(
        focus=focus,
        mr_title=mr_title,
        mr_description=mr_description,
        existing_discussions=existing_discussions,
        annotated_diff=annotated_diff,
    )
    raw = client.complete(system=SYSTEM_PROMPT, user=user, model=model)
    return parse_findings_response(raw, focus=focus)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/review/test_llm.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/llm.py tests/review/test_llm.py
git commit -m "feat(review): add Anthropic wrapper and findings JSON parser"
```

---

## Task 12: `review/dedup.py` — marker extraction and filtering

**Files:**
- Create: `src/tanuki_slice/review/dedup.py`
- Create: `tests/review/test_dedup.py`

- [ ] **Step 1: Write failing tests**

`tests/review/test_dedup.py`:

```python
from tanuki_slice.review.dedup import (
    MARKER_REGEX,
    extract_markers,
    filter_new,
    render_marker,
)
from tanuki_slice.review.findings import Finding


def _finding(title: str = "t") -> Finding:
    return Finding(
        file_path="a.py",
        line=1,
        severity="warning",
        title=title,
        body="b",
        focus="correctness",
    )


def test_render_marker_shape() -> None:
    m = render_marker("abc123abc123")
    assert m == "<!-- tanuki:abc123abc123 -->"


def test_extract_markers_from_body() -> None:
    body = "inline note\n<!-- tanuki:deadbeef1234 -->\ntrailing"
    assert extract_markers(body) == {"deadbeef1234"}


def test_extract_markers_multiple() -> None:
    body = "<!-- tanuki:aaaaaaaaaaaa --> <!-- tanuki:bbbbbbbbbbbb -->"
    assert extract_markers(body) == {"a" * 12, "b" * 12}


def test_marker_regex_ignores_unknown_format() -> None:
    assert not MARKER_REGEX.search("<!-- tanuki:xyz -->")  # too short


def test_filter_new_splits_posted_vs_skipped() -> None:
    f1 = _finding(title="a")
    f2 = _finding(title="b")
    existing = {f1.fingerprint}
    to_post, skipped = filter_new([f1, f2], existing)
    assert to_post == [f2]
    assert skipped == [f1]
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/review/test_dedup.py -v
```

Expected: module missing.

- [ ] **Step 3: Implement `dedup.py`**

```python
"""Dedup via fingerprint markers embedded in posted comment bodies."""

from __future__ import annotations

import re
from typing import Any

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.review.findings import Finding

MARKER_REGEX = re.compile(r"<!--\s*tanuki:([0-9a-f]{12})\s*-->")


def render_marker(fingerprint: str) -> str:
    return f"<!-- tanuki:{fingerprint} -->"


def extract_markers(body: str) -> set[str]:
    return set(MARKER_REGEX.findall(body))


def fetch_existing_markers(
    client: GitLabClient, project_id: int, mr_iid: int
) -> set[str]:
    markers: set[str] = set()
    notes: list[dict[str, Any]] = client.get_mr_notes(project_id, mr_iid)
    for note in notes:
        body = note.get("body") or ""
        markers.update(extract_markers(body))
    discussions = client.get_mr_discussions(project_id, mr_iid)
    for disc in discussions:
        for note in disc.get("notes") or []:
            body = note.get("body") or ""
            markers.update(extract_markers(body))
    return markers


def filter_new(
    findings: list[Finding], existing_markers: set[str]
) -> tuple[list[Finding], list[Finding]]:
    to_post: list[Finding] = []
    skipped: list[Finding] = []
    for f in findings:
        if f.fingerprint in existing_markers:
            skipped.append(f)
        else:
            to_post.append(f)
    return to_post, skipped
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/review/test_dedup.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/dedup.py tests/review/test_dedup.py
git commit -m "feat(review): add fingerprint-based dedup"
```

---

## Task 13: `review/poster.py` — render + post inline and summary

**Files:**
- Create: `src/tanuki_slice/review/poster.py`
- Create: `tests/review/test_poster.py`

- [ ] **Step 1: Write failing tests**

`tests/review/test_poster.py`:

```python
from tanuki_slice.review.diff import DiffPosition
from tanuki_slice.review.findings import Finding
from tanuki_slice.review.poster import (
    render_inline_body,
    render_summary,
)


def _finding(**overrides: object) -> Finding:
    base: dict[str, object] = {
        "file_path": "a.py",
        "line": 42,
        "severity": "warning",
        "title": "missing await",
        "body": "details",
        "focus": "correctness",
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


def test_render_inline_body_appends_marker() -> None:
    f = _finding()
    body = render_inline_body(f)
    assert body.startswith("**warning** missing await")
    assert "details" in body
    assert f"<!-- tanuki:{f.fingerprint} -->" in body


def test_render_summary_lists_findings_grouped() -> None:
    a = _finding(title="issue a", severity="blocker")
    b = _finding(title="issue b", line=10, severity="nit")
    out = render_summary([a, b])
    assert "Tanuki review" in out
    assert "1 blocker" in out
    assert "1 nit" in out
    assert "a.py:42" in out
    assert "a.py:10" in out
    assert f"<!-- tanuki:{a.fingerprint} -->" in out
    assert f"<!-- tanuki:{b.fingerprint} -->" in out


def test_gitlab_position_payload_has_required_keys() -> None:
    pos = DiffPosition(
        base_sha="b",
        start_sha="s",
        head_sha="h",
        old_path="a.py",
        new_path="a.py",
        new_line=3,
        old_line=None,
    )
    payload = pos.as_gitlab_payload()
    for k in ("base_sha", "start_sha", "head_sha", "new_path", "new_line", "position_type"):
        assert k in payload
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/review/test_poster.py -v
```

Expected: module missing.

- [ ] **Step 3: Implement `poster.py`**

```python
"""Render + post review findings (inline discussions and a summary note)."""

from __future__ import annotations

from collections import Counter

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.review.dedup import render_marker
from tanuki_slice.review.diff import DiffPosition
from tanuki_slice.review.findings import Finding


def render_inline_body(finding: Finding) -> str:
    return (
        f"**{finding.severity}** {finding.title}\n\n"
        f"{finding.body}\n\n"
        f"_focus: {finding.focus}_\n\n"
        f"{render_marker(finding.fingerprint)}"
    )


def render_summary(findings: list[Finding]) -> str:
    if not findings:
        return "## Tanuki review\n\nNo findings.\n"

    counts = Counter(f.severity for f in findings)
    order = ["blocker", "warning", "nit"]
    count_line = ", ".join(f"{counts.get(k, 0)} {k}" for k in order if counts.get(k, 0))

    lines: list[str] = [
        "## Tanuki review",
        "",
        f"{len(findings)} finding{'s' if len(findings) != 1 else ''} ({count_line}).",
        "",
    ]
    for f in findings:
        lines.append(
            f"- **{f.severity}** [`{f.file_path}:{f.line}`] {f.title} "
            f"{render_marker(f.fingerprint)}"
        )
    lines.append("")
    return "\n".join(lines)


def post_inline(
    client: GitLabClient,
    project_id: int,
    mr_iid: int,
    finding: Finding,
    position: DiffPosition,
) -> None:
    body = render_inline_body(finding)
    client.create_mr_discussion(project_id, mr_iid, body, position.as_gitlab_payload())


def post_summary(
    client: GitLabClient, project_id: int, mr_iid: int, findings: list[Finding]
) -> None:
    body = render_summary(findings)
    client.create_mr_note(project_id, mr_iid, body)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/review/test_poster.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/poster.py tests/review/test_poster.py
git commit -m "feat(review): add inline and summary comment poster"
```

---

## Task 14: `review/orchestrator.py` — end-to-end glue

**Files:**
- Create: `src/tanuki_slice/review/orchestrator.py`
- Create: `tests/review/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

`tests/review/test_orchestrator.py`:

```python
from dataclasses import replace
from typing import Any

from tanuki_slice.review.config import ReviewConfig
from tanuki_slice.review.diff import (
    DiffHunk,
    DiffLine,
    FileDiff,
    MRDiff,
)
from tanuki_slice.review.findings import Finding
from tanuki_slice.review.orchestrator import run_review_flow


class FakeGitLabClient:
    def __init__(self) -> None:
        self.posted_notes: list[str] = []
        self.posted_discussions: list[tuple[str, dict[str, Any]]] = []

    def get_mr(self, project_id: int, mr_iid: int) -> dict[str, Any]:
        return {
            "title": "fix things",
            "description": "body",
            "source_branch": "feat",
            "target_branch": "main",
            "author": {"username": "alice"},
            "web_url": "https://x",
            "diff_refs": {"base_sha": "b", "start_sha": "s", "head_sha": "h"},
        }

    def get_mr_diffs(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        return [
            {
                "old_path": "a.py",
                "new_path": "a.py",
                "new_file": False,
                "deleted_file": False,
                "renamed_file": False,
                "diff": "@@ -1,1 +1,2 @@\n x\n+y\n",
            }
        ]

    def get_mr_discussions(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        return []

    def get_mr_notes(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        return []

    def create_mr_note(self, project_id: int, mr_iid: int, body: str) -> dict[str, Any]:
        self.posted_notes.append(body)
        return {"id": 1}

    def create_mr_discussion(
        self,
        project_id: int,
        mr_iid: int,
        body: str,
        position: dict[str, Any],
    ) -> dict[str, Any]:
        self.posted_discussions.append((body, position))
        return {"id": "d1"}


class FakeLLM:
    def __init__(self, findings_per_focus: dict[str, list[Finding]]) -> None:
        self._findings = findings_per_focus

    def review(self, focus: str, context: dict[str, str]) -> list[Finding]:
        return self._findings.get(focus, [])


def _cfg(**overrides: Any) -> ReviewConfig:
    base = ReviewConfig(
        project_id=1,
        mr_iid=2,
        focus=["correctness"],
        model="claude-sonnet-4-6",
        max_findings=10,
        max_diff_tokens=150_000,
        dry_run=False,
        yes=True,
        gitlab_url="https://gitlab.com",
        gitlab_token="t",
        anthropic_api_key="k",
    )
    return replace(base, **overrides)


def test_dry_run_posts_nothing() -> None:
    client = FakeGitLabClient()
    llm = FakeLLM(
        {
            "correctness": [
                Finding(
                    file_path="a.py",
                    line=2,
                    severity="warning",
                    title="t",
                    body="b",
                    focus="correctness",
                )
            ]
        }
    )
    result = run_review_flow(_cfg(dry_run=True), gitlab=client, llm=llm)
    assert result.dry_run is True
    assert client.posted_notes == []
    assert client.posted_discussions == []
    assert len(result.findings) == 1


def test_posts_inline_and_summary_for_new_finding() -> None:
    client = FakeGitLabClient()
    f = Finding(
        file_path="a.py",
        line=2,
        severity="warning",
        title="t",
        body="b",
        focus="correctness",
    )
    result = run_review_flow(_cfg(), gitlab=client, llm=FakeLLM({"correctness": [f]}))
    assert result.posted_inline == 1
    assert result.posted_summary is True
    assert len(client.posted_discussions) == 1
    assert len(client.posted_notes) == 1


def test_skips_dedup_against_existing_marker() -> None:
    client = FakeGitLabClient()
    f = Finding(
        file_path="a.py",
        line=2,
        severity="warning",
        title="t",
        body="b",
        focus="correctness",
    )
    client.get_mr_notes = lambda *a, **k: [  # type: ignore[assignment]
        {"body": f"seen <!-- tanuki:{f.fingerprint} -->"}
    ]
    result = run_review_flow(_cfg(), gitlab=client, llm=FakeLLM({"correctness": [f]}))
    assert result.posted_inline == 0
    assert result.posted_summary is False
    assert len(result.skipped_dedup) == 1


def test_demotes_finding_without_position_to_summary() -> None:
    client = FakeGitLabClient()
    # Line 999 not in diff → position_for returns None → demoted to summary.
    f = Finding(
        file_path="a.py",
        line=999,
        severity="warning",
        title="t",
        body="b",
        focus="correctness",
    )
    result = run_review_flow(_cfg(), gitlab=client, llm=FakeLLM({"correctness": [f]}))
    assert result.posted_inline == 0
    assert len(client.posted_discussions) == 0
    assert result.posted_summary is True
    assert len(result.demoted_to_summary) == 1


def test_enforces_max_findings_cap() -> None:
    client = FakeGitLabClient()
    findings = [
        Finding(
            file_path="a.py",
            line=2,
            severity="warning",
            title=f"t{i}",
            body="b",
            focus="correctness",
        )
        for i in range(5)
    ]
    result = run_review_flow(
        _cfg(max_findings=2),
        gitlab=client,
        llm=FakeLLM({"correctness": findings}),
    )
    assert len(result.findings) == 2
```

- [ ] **Step 2: Confirm failure**

```bash
uv run pytest tests/review/test_orchestrator.py -v
```

Expected: module missing.

- [ ] **Step 3: Implement `orchestrator.py`**

```python
"""End-to-end review flow: fetch, prompt, parse, dedup, post."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from tanuki_slice.core.chunker import chunk_threads
from tanuki_slice.core.client import GitLabClient
from tanuki_slice.core.scraper import scrape_mr
from tanuki_slice.review.config import ReviewConfig
from tanuki_slice.review.dedup import (
    fetch_existing_markers,
    filter_new,
)
from tanuki_slice.review.diff import (
    MRDiff,
    fetch_mr_diff,
    position_for,
    render_for_prompt,
)
from tanuki_slice.review.findings import Finding
from tanuki_slice.review.poster import post_inline, post_summary


class DiffTooLarge(Exception):
    def __init__(self, tokens: int, limit: int) -> None:
        self.tokens = tokens
        self.limit = limit
        super().__init__(f"Diff too large: ~{tokens} tokens exceeds limit of {limit}")


class GitLabProtocol(Protocol):
    def get_mr(self, project_id: int, mr_iid: int) -> dict: ...  # type: ignore[type-arg]
    def get_mr_diffs(self, project_id: int, mr_iid: int) -> list[dict]: ...  # type: ignore[type-arg]
    def get_mr_discussions(self, project_id: int, mr_iid: int) -> list[dict]: ...  # type: ignore[type-arg]
    def get_mr_notes(self, project_id: int, mr_iid: int) -> list[dict]: ...  # type: ignore[type-arg]
    def create_mr_note(self, project_id: int, mr_iid: int, body: str) -> dict: ...  # type: ignore[type-arg]
    def create_mr_discussion(
        self, project_id: int, mr_iid: int, body: str, position: dict  # type: ignore[type-arg]
    ) -> dict: ...  # type: ignore[type-arg]


class LLMReviewer(Protocol):
    def review(self, focus: str, context: dict[str, str]) -> list[Finding]: ...


@dataclass
class ReviewResult:
    findings: list[Finding] = field(default_factory=list)
    skipped_dedup: list[Finding] = field(default_factory=list)
    demoted_to_summary: list[Finding] = field(default_factory=list)
    posted_inline: int = 0
    posted_summary: bool = False
    dry_run: bool = False


def _render_existing_discussions(
    client: GitLabProtocol, config: ReviewConfig
) -> str:
    # Only unresolved discussions for context; resolved ones tell us what's fixed
    # already — we can skip them for MVP since the spec says include unresolved.
    try:
        metadata, threads = scrape_mr(client, config.project_id, config.mr_iid)  # type: ignore[arg-type]
    except Exception:
        return ""
    chunks = chunk_threads(metadata, threads, token_budget=8000, include_resolved=False)
    if not chunks:
        return ""
    lines: list[str] = []
    for chunk in chunks:
        for file_path, ts in chunk.file_groups.items():
            for t in ts:
                lines.append(f"- {file_path}:{t.line}: " + "; ".join(n.body for n in t.notes))
    return "\n".join(lines)


def run_review_flow(
    config: ReviewConfig,
    *,
    gitlab: GitLabProtocol,
    llm: LLMReviewer,
) -> ReviewResult:
    diff: MRDiff = fetch_mr_diff(gitlab, config.project_id, config.mr_iid)  # type: ignore[arg-type]

    if diff.estimated_tokens > config.max_diff_tokens:
        raise DiffTooLarge(diff.estimated_tokens, config.max_diff_tokens)

    mr = gitlab.get_mr(config.project_id, config.mr_iid)
    existing_discussions = _render_existing_discussions(gitlab, config)
    annotated = render_for_prompt(diff)

    context = {
        "mr_title": mr.get("title") or "",
        "mr_description": mr.get("description") or "",
        "existing_discussions": existing_discussions,
        "annotated_diff": annotated,
    }

    all_findings: list[Finding] = []
    for focus in config.focus:
        all_findings.extend(llm.review(focus, context))

    # dedup against MR history
    existing_markers = fetch_existing_markers(gitlab, config.project_id, config.mr_iid)  # type: ignore[arg-type]
    to_post, skipped = filter_new(all_findings, existing_markers)

    # apply cap
    to_post = to_post[: config.max_findings]

    # position mapping
    inline_ready: list[tuple[Finding, object]] = []
    demoted: list[Finding] = []
    for f in to_post:
        pos = position_for(diff, f.file_path, f.line)
        if pos is None:
            demoted.append(f)
        else:
            inline_ready.append((f, pos))

    result = ReviewResult(
        findings=to_post,
        skipped_dedup=skipped,
        demoted_to_summary=demoted,
        dry_run=config.dry_run,
    )

    if config.dry_run:
        return result

    if not to_post:
        return result

    for finding, position in inline_ready:
        post_inline(
            gitlab,  # type: ignore[arg-type]
            config.project_id,
            config.mr_iid,
            finding,
            position,  # type: ignore[arg-type]
        )
        result.posted_inline += 1

    post_summary(gitlab, config.project_id, config.mr_iid, to_post)  # type: ignore[arg-type]
    result.posted_summary = True
    return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/review/test_orchestrator.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/tanuki_slice/review/orchestrator.py tests/review/test_orchestrator.py
git commit -m "feat(review): wire end-to-end review flow in orchestrator"
```

---

## Task 15: Wire `review` CLI subcommand

**Files:**
- Modify: `src/tanuki_slice/cli.py`

- [ ] **Step 1: Add the `review` subcommand to `cli.py`**

Append to `cli.py` (keep the existing `chunk_cmd`; don't delete anything):

```python
import os
from urllib.error import URLError

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.review.config import ReviewConfig
from tanuki_slice.review.llm import AnthropicClient, run_review
from tanuki_slice.review.orchestrator import DiffTooLarge, run_review_flow


class _AnthropicReviewer:
    def __init__(self, client: AnthropicClient, model: str) -> None:
        self._client = client
        self._model = model

    def review(self, focus: str, context: dict[str, str]) -> list:  # type: ignore[type-arg]
        return run_review(
            self._client,
            model=self._model,
            focus=focus,
            mr_title=context["mr_title"],
            mr_description=context["mr_description"],
            existing_discussions=context["existing_discussions"],
            annotated_diff=context["annotated_diff"],
        )


@app.command("review")
def review_cmd(
    project_id: Annotated[int, typer.Option("--project-id", help="GitLab project ID")],
    mr_iid: Annotated[int, typer.Option("--mr-iid", help="Merge request IID")],
    focus: Annotated[
        list[str],
        typer.Option("--focus", help="Review focus: correctness|security|style|all"),
    ] = ["correctness"],
    model: Annotated[
        str | None, typer.Option("--model", help="Anthropic model ID")
    ] = None,
    max_findings: Annotated[
        int | None, typer.Option("--max-findings", help="Cap on findings posted")
    ] = None,
    max_diff_tokens: Annotated[
        int | None,
        typer.Option("--max-diff-tokens", help="Fail if diff exceeds this estimate"),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print findings, do not post")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Skip interactive confirm")] = False,
    gitlab_url: Annotated[
        str | None, typer.Option("--gitlab-url", help="GitLab instance URL")
    ] = None,
    config: Annotated[
        Path | None, typer.Option("--config", help="Path to tanuki.toml")
    ] = None,
) -> None:
    """Review a GitLab MR with Claude and post inline + summary comments."""
    try:
        cfg = ReviewConfig.load(
            cli={
                "project_id": project_id,
                "mr_iid": mr_iid,
                "focus": focus,
                "model": model,
                "max_findings": max_findings,
                "max_diff_tokens": max_diff_tokens,
                "dry_run": dry_run,
                "yes": yes,
                "gitlab_url": gitlab_url,
            },
            env=dict(os.environ),
            toml_path=config or Path("tanuki.toml"),
        )
    except ValueError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    gitlab = GitLabClient(cfg.gitlab_url, cfg.gitlab_token)
    anthropic = AnthropicClient(cfg.anthropic_api_key)
    reviewer = _AnthropicReviewer(anthropic, cfg.model)

    if not cfg.yes and not cfg.dry_run:
        typer.echo(
            f"About to review MR !{cfg.mr_iid} with focus={cfg.focus} "
            f"and post up to {cfg.max_findings} findings. Continue? [y/N]"
        )
        answer = input().strip().lower()
        if answer not in {"y", "yes"}:
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

    try:
        result = run_review_flow(cfg, gitlab=gitlab, llm=reviewer)
    except DiffTooLarge as exc:
        typer.echo(
            f"Diff too large: ~{exc.tokens} tokens exceeds limit of {exc.limit}. "
            "Reduce MR scope or raise --max-diff-tokens.",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    except GitLabAPIError as exc:
        typer.echo(f"GitLab API error {exc.status}: {exc.reason}", err=True)
        raise typer.Exit(code=1) from exc
    except URLError as exc:
        typer.echo(f"Network error: {exc.reason}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"Findings: {len(result.findings)} | "
        f"posted inline: {result.posted_inline} | "
        f"summary: {result.posted_summary} | "
        f"skipped (dedup): {len(result.skipped_dedup)} | "
        f"demoted: {len(result.demoted_to_summary)} | "
        f"dry_run: {result.dry_run}"
    )
```

- [ ] **Step 2: Verify CLI help**

```bash
uv run tanuki-slice --help
uv run tanuki-slice review --help
```

Expected: both commands listed; `review --help` shows all flags.

- [ ] **Step 3: Run full suite**

```bash
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/tanuki_slice/cli.py
git commit -m "feat(cli): wire tanuki-slice review subcommand"
```

---

## Task 16: Update CHANGELOG and README

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`

- [ ] **Step 1: Add 0.2.0 entry to `CHANGELOG.md`**

Insert a new section under `## [Unreleased]`:

```markdown
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
```

Append at the bottom:

```markdown
[0.2.0]: https://github.com/tomtom103/tanuki-slice/compare/v0.1.0...v0.2.0
```

And update the `[Unreleased]` compare link to `v0.2.0...HEAD`.

- [ ] **Step 2: Update README — flip Roadmap section into Usage**

In `README.md`:
1. Under `## Usage`, add a subsection header `### \`chunk\` — split MR discussions` above the existing CLI examples; change every `tanuki-slice --project-id ...` example to `tanuki-slice chunk --project-id ...`.
2. Add a new subsection `### \`review\` — LLM code review` with concrete examples:

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

3. In the **Configuration** table add rows for `ANTHROPIC_API_KEY` (required for `review`) and mention that `tanuki.toml` `[review]` keys map to CLI flags.
4. Replace the `## Roadmap` section (now shipped) with a shorter `## Status` paragraph: "The `chunk` and `review` commands are available. Future work: webhook daemon, multi-provider LLMs, cross-chunk review for mega-MRs."

- [ ] **Step 3: Run final checks**

```bash
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -q
uv run tanuki-slice --help
uv run tanuki-slice chunk --help
uv run tanuki-slice review --help
uv build
```

Expected: everything green; build produces `dist/tanuki_slice-0.2.0*`.

- [ ] **Step 4: Clean build artifacts**

```bash
rm -rf dist/
```

- [ ] **Step 5: Commit + push**

```bash
git add CHANGELOG.md README.md
git commit -m "docs: 0.2.0 changelog + usage for review subcommand"
git push
```

---

## Self-Review

**Spec coverage:**

- CLI-only interface → Tasks 3, 15.
- Anthropic backend → Task 11.
- Inline + summary output → Task 13.
- Stateless fingerprint dedup → Tasks 5, 12.
- `--focus` flag + prompts → Tasks 6, 10.
- Existing-discussions context → Task 14 (`_render_existing_discussions`).
- Post-by-default + cap + confirm + dry-run + `--yes` → Tasks 14, 15.
- TOML config + flag precedence → Task 6.
- Fail-fast on oversized diff → Task 14 (`DiffTooLarge`).
- `core/` + `review/` layout → Tasks 1, 2, and the new-file tasks.
- All data model fields from spec (`Finding`, `MRDiff`, `DiffPosition`, `ReviewConfig`, `ReviewResult`) → Tasks 5, 6, 8, 14.
- New GitLab client methods → Task 7.
- Testing strategy (unit pure functions + fake clients) → each feature task.
- Migration note (0.2.0 BREAKING) + doc updates → Task 16.

All spec requirements covered.

**Placeholder scan:** No `TBD`, `TODO`, "implement later", "similar to Task N" shortcuts. Every task has concrete code.

**Type consistency:**

- `Finding` fields are referenced identically in `findings.py`, `dedup.py`, `poster.py`, `llm.py`, and `orchestrator.py`.
- `DiffPosition.as_gitlab_payload()` is defined in Task 8 and called in Task 13.
- `ReviewConfig.load(cli, env, toml_path)` signature is identical in Task 6 tests and Task 15 CLI.
- `LLMReviewer.review(focus, context)` Protocol matches `_AnthropicReviewer.review` in Task 15 and `FakeLLM.review` in Task 14.
- `GitLabProtocol` method set matches what `FakeGitLabClient` implements in Task 14.

Plan is internally consistent.
