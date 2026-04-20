"""Tests for ReviewConfig loading: CLI > TOML > env defaults."""

from __future__ import annotations

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
