"""Prompt templates for the review bot."""
# ruff: noqa: E501

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
