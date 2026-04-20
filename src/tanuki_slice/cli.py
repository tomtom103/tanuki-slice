"""CLI interface for tanuki-slice."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated
from urllib.error import URLError

import typer

from tanuki_slice.chunker import GitLabMRChunker
from tanuki_slice.client import GitLabAPIError

app = typer.Typer(
    name="tanuki-slice",
    help="Scrape GitLab MR comments and split into LLM-ready chunks.",
    add_completion=False,
)


@app.command()
def main(
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
