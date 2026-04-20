"""CLI interface for tanuki-slice."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated
from urllib.error import URLError

import typer

from tanuki_slice.core.chunker import GitLabMRChunker
from tanuki_slice.core.client import GitLabAPIError, GitLabClient
from tanuki_slice.review.config import ReviewConfig
from tanuki_slice.review.findings import Finding
from tanuki_slice.review.llm import AnthropicClient, run_review
from tanuki_slice.review.orchestrator import DiffTooLarge, run_review_flow

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


class _AnthropicReviewer:
    def __init__(self, client: AnthropicClient, model: str) -> None:
        self._client = client
        self._model = model

    def review(self, focus: str, context: dict[str, str]) -> list[Finding]:
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
    ] = ["correctness"],  # noqa: B006
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
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print findings, do not post")
    ] = False,
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


if __name__ == "__main__":
    sys.exit(app())
