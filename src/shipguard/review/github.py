from __future__ import annotations

import base64
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError


class ReviewError(RuntimeError):
    """Raised when a pull-request review cannot be safely completed."""


class PullRequestFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str
    patch: str | None = None


class PullRequestRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str


class PullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base: PullRequestRef
    head: PullRequestRef

    @property
    def base_sha(self) -> str:
        return self.base.sha

    @property
    def head_sha(self) -> str:
        return self.head.sha


class GitHubClient:
    def __init__(self, token: str, *, client: httpx.Client | None = None) -> None:
        if not token:
            raise ReviewError("A GitHub token is required")
        self._client = client or httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, params=params, **kwargs)
        except httpx.RequestError as exc:
            raise ReviewError(f"GitHub API request failed: {exc}") from exc
        if response.is_error:
            raise ReviewError(
                f"GitHub API {method} {path} returned {response.status_code}"
            )
        return response

    def get_pull_request(self, owner: str, repository: str, number: int) -> PullRequest:
        response = self._request(
            "GET", f"/repos/{owner}/{repository}/pulls/{number}"
        )
        try:
            return PullRequest.model_validate(response.json())
        except (ValueError, ValidationError, KeyError) as exc:
            raise ReviewError("GitHub returned invalid pull-request metadata") from exc

    def get_pull_request_files(
        self,
        owner: str,
        repository: str,
        number: int,
        *,
        max_files: int,
    ) -> list[PullRequestFile]:
        files: list[PullRequestFile] = []
        page = 1
        while True:
            response = self._request(
                "GET",
                f"/repos/{owner}/{repository}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            try:
                page_files = response.json()
            except ValueError as exc:
                raise ReviewError("GitHub returned invalid pull-request file data") from exc
            if not isinstance(page_files, list):
                raise ReviewError("GitHub pull-request files response must be an array")
            try:
                files.extend(PullRequestFile.model_validate(item) for item in page_files)
            except (ValidationError, TypeError) as exc:
                raise ReviewError("GitHub returned an invalid pull-request file") from exc
            if len(files) > max_files:
                raise ReviewError(
                    f"Pull request changes {len(files)} files; the configured limit "
                    f"is {max_files}"
                )
            if len(page_files) < 100:
                return files
            page += 1

    def get_base_agents(self, owner: str, repository: str, base_sha: str) -> str:
        try:
            response = self._client.get(
                f"/repos/{owner}/{repository}/contents/AGENTS.md",
                params={"ref": base_sha},
            )
        except httpx.RequestError as exc:
            raise ReviewError(f"GitHub API request failed: {exc}") from exc
        if response.status_code == 404:
            return ""
        if response.is_error:
            raise ReviewError(
                f"GitHub API could not fetch base AGENTS.md: {response.status_code}"
            )
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ReviewError("GitHub returned invalid base AGENTS.md metadata")
            if payload.get("encoding") != "base64":
                raise ReviewError("GitHub returned AGENTS.md in an unsupported encoding")
            content = payload["content"]
            return base64.b64decode("".join(content.split()), validate=True).decode(
                "utf-8"
            )
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise ReviewError("GitHub returned invalid base AGENTS.md content") from exc

    def post_inline_comment(
        self,
        owner: str,
        repository: str,
        number: int,
        *,
        head_sha: str,
        finding: dict[str, Any],
    ) -> None:
        self._request(
            "POST",
            f"/repos/{owner}/{repository}/pulls/{number}/comments",
            json={
                "body": finding["comment"],
                "commit_id": head_sha,
                "path": finding["file"],
                "line": finding["line"],
                "side": "RIGHT",
            },
        )
