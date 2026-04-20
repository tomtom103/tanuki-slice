"""Findings produced by the reviewer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

Severity = Literal["blocker", "warning", "nit"]


@dataclass(frozen=True)
class Finding:
    file_path: str
    line: int
    severity: Severity
    title: str
    body: str
    focus: str

    @property
    def fingerprint(self) -> str:
        raw = f"{self.file_path}|{self.line}|{self.focus}|{self.title}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
