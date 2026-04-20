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
