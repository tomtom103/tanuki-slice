"""End-to-end review flow tests with fake GitLab + LLM."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from tanuki_slice.review.config import ReviewConfig
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
