"""Review configuration: CLI flags + env + TOML precedence."""

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
    ) -> ReviewConfig:
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
