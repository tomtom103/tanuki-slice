"""Render + post review findings (inline discussions and a summary note)."""

from __future__ import annotations

from collections import Counter

from tanuki_slice.core.client import GitLabClient
from tanuki_slice.review.dedup import render_marker
from tanuki_slice.review.diff import DiffPosition
from tanuki_slice.review.findings import Finding, Severity


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
    order: list[Severity] = ["blocker", "warning", "nit"]
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
