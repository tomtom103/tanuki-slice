"""Minimal GitLab REST API client using only stdlib."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitLabAPIError(Exception):
    """Raised when the GitLab API returns an error response."""

    def __init__(self, status: int, reason: str, url: str) -> None:
        self.status = status
        self.reason = reason
        self.url = url
        super().__init__(f"GitLab API {status} {reason} for {url}")


class GitLabClient:
    """Minimal GitLab REST API client using only stdlib."""

    def __init__(self, gitlab_url: str, token: str) -> None:
        self.base_url = gitlab_url.rstrip("/")
        self.token = token

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}/api/v4{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        results: list[Any] = []

        next_url: str | None = url
        while next_url:
            this_url = next_url
            req = Request(this_url, headers={"PRIVATE-TOKEN": self.token})
            try:
                with urlopen(req) as resp:  # noqa: S310
                    data = json.loads(resp.read().decode())
                    if not isinstance(data, list):
                        return data
                    results.extend(data)
                    link = resp.headers.get("Link", "")
                    next_url = self._parse_next_link(link)
            except HTTPError as exc:
                reason = self._extract_reason(exc)
                raise GitLabAPIError(exc.code, reason, this_url) from exc

        return results

    @staticmethod
    def _extract_reason(exc: HTTPError) -> str:
        try:
            body = exc.read().decode()
            payload = json.loads(body)
            if isinstance(payload, dict):
                for key in ("message", "error", "error_description"):
                    value = payload.get(key)
                    if isinstance(value, str) and value:
                        return value
        except (OSError, ValueError, UnicodeDecodeError):
            pass
        return str(exc.reason) or "Unknown error"

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        """Extract the 'next' URL from a Link header."""
        for part in link_header.split(","):
            if 'rel="next"' in part:
                match = re.search(r"<(.+?)>", part)
                if match:
                    return match.group(1)
        return None

    def get_mr(self, project_id: int, mr_iid: int) -> dict[str, Any]:
        pid = quote(str(project_id), safe="")
        result: dict[str, Any] = self._get(f"/projects/{pid}/merge_requests/{mr_iid}")
        return result

    def get_mr_discussions(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        pid = quote(str(project_id), safe="")
        result: list[dict[str, Any]] = self._get(
            f"/projects/{pid}/merge_requests/{mr_iid}/discussions",
            params={"per_page": "100"},
        )
        return result
