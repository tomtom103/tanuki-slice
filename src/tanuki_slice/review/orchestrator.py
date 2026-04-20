"""End-to-end review flow: fetch, prompt, parse, dedup, post."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from tanuki_slice.core.chunker import chunk_threads
from tanuki_slice.core.scraper import scrape_mr
from tanuki_slice.review.config import ReviewConfig
from tanuki_slice.review.dedup import (
    fetch_existing_markers,
    filter_new,
)
from tanuki_slice.review.diff import (
    DiffPosition,
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
    def get_mr(self, project_id: int, mr_iid: int) -> dict[str, Any]: ...
    def get_mr_diffs(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]: ...
    def get_mr_discussions(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]: ...
    def get_mr_notes(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]: ...
    def create_mr_note(
        self, project_id: int, mr_iid: int, body: str
    ) -> dict[str, Any]: ...
    def create_mr_discussion(
        self, project_id: int, mr_iid: int, body: str, position: dict[str, Any]
    ) -> dict[str, Any]: ...


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


def _render_existing_discussions(client: GitLabProtocol, config: ReviewConfig) -> str:
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
                joined = "; ".join(n.body for n in t.notes)
                lines.append(f"- {file_path}:{t.line}: {joined}")
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

    existing_markers = fetch_existing_markers(gitlab, config.project_id, config.mr_iid)  # type: ignore[arg-type]
    to_post, skipped = filter_new(all_findings, existing_markers)

    to_post = to_post[: config.max_findings]

    inline_ready: list[tuple[Finding, DiffPosition]] = []
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
            position,
        )
        result.posted_inline += 1

    post_summary(gitlab, config.project_id, config.mr_iid, to_post)  # type: ignore[arg-type]
    result.posted_summary = True
    return result
