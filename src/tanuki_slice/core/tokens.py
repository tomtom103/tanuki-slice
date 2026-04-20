"""Rough token estimation helpers."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/code mixed content."""
    return max(1, len(text) // 4)
