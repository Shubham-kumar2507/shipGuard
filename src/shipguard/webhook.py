from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import httpx
import jwt
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shipguard.config import Config, load_config
from shipguard.models import Report, Severity

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-fA-F]{40,64}$")
_SUPPORTED_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review"}


class WebhookError(RuntimeError):
    """Raised when a GitHub App webhook cannot be processed safely."""


class WebhookSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook_secret: str = Field(min_length=1)
    app_id: str = Field(min_length=1)
    app_private_key: str = Field(min_length=1)
    max_payload_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)

    @classmethod
    def from_environment(cls) -> WebhookSettings:
        values = {
            "webhook_secret": os.environ.get("SHIPGUARD_WEBHOOK_SECRET", ""),
            "app_id": os.environ.get("SHIPGUARD_APP_ID", ""),
            "app_private_key": os.environ.get(
                "SHIPGUARD_APP_PRIVATE_KEY", ""
            ).replace("\\n", "\n"),
        }
        try:
            return cls.model_validate(values)
        except ValidationError as exc:
            raise WebhookError(
                "SHIPGUARD_WEBHOOK_SECRET, SHIPGUARD_APP_ID, and "
                "SHIPGUARD_APP_PRIVATE_KEY must be configured"
            ) from exc


class Installation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)


class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class PullRequestRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str = Field(pattern=r"^[0-9a-fA-F]{40,64}$")


class PullRequestEventData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int = Field(gt=0)
    base: PullRequestRef
    head: PullRequestRef


class PullRequestEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str
    installation: Installation
    repository: Repository
    pull_request: PullRequestEventData


class GitHubAppClient:
    def __init__(
        self, settings: WebhookSettings, *, client: httpx.Client | None = None
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = self._client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {token}"},
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise WebhookError(f"GitHub API request failed: {exc}") from exc
        if response.is_error:
            raise WebhookError(
                f"GitHub API {method} {path} returned {response.status_code}"
            )
        return response

    def create_installation_token(self, installation_id: int) -> str:
        app_jwt = self._create_app_jwt()
        response = self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            token=app_jwt,
        )
        try:
            token = response.json()["token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise WebhookError("GitHub returned an invalid installation token") from exc
        if not isinstance(token, str) or not token:
            raise WebhookError("GitHub returned an empty installation token")
        return token

    def create_check_run(
        self, repository: str, head_sha: str, token: str, delivery_id: str
    ) -> int:
        response = self._request(
            "POST",
            f"/repos/{repository}/check-runs",
            token=token,
            json={
                "name": "ShipGuard",
                "head_sha": head_sha,
                "status": "in_progress",
                "external_id": delivery_id,
            },
        )
        try:
            check_id = response.json()["id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise WebhookError("GitHub returned an invalid Check Run") from exc
        if not isinstance(check_id, int) or check_id < 1:
            raise WebhookError("GitHub returned an invalid Check Run id")
        return check_id

    def complete_check_run(
        self,
        repository: str,
        check_id: int,
        token: str,
        *,
        conclusion: str,
        title: str,
        summary: str,
        annotations: list[dict[str, Any]],
    ) -> None:
        self._request(
            "PATCH",
            f"/repos/{repository}/check-runs/{check_id}",
            token=token,
            json={
                "status": "completed",
                "conclusion": conclusion,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "output": {
                    "title": title,
                    "summary": summary[:60_000],
                    "annotations": annotations[:50],
                },
            },
        )

    def _create_app_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 540,
            "iss": self._settings.app_id,
        }
        try:
            return jwt.encode(
                payload, self._settings.app_private_key, algorithm="RS256"
            )
        except (jwt.PyJWTError, ValueError) as exc:
            raise WebhookError("Unable to sign GitHub App JWT") from exc


def _signature_is_valid(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    supplied_digest = signature.removeprefix("sha256=")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", supplied_digest):
        return False
    expected_digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_digest, supplied_digest.lower())


def _git_environment(token: str, home: Path) -> dict[str, str]:
    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {encoded}",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


def _run_git(args: list[str], *, cwd: Path, environment: dict[str, str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise WebhookError("Git is not installed on the webhook runner") from exc
    except subprocess.TimeoutExpired as exc:
        raise WebhookError("Git operation exceeded its timeout") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no error output"
        raise WebhookError(f"Git operation failed: {detail[:1000]}")
    return result.stdout.strip()


def _safe_cli_environment() -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": os.environ.get("HOME", str(Path(sys.prefix))),
    }
    for name, value in os.environ.items():
        upper_name = name.upper()
        if name.startswith(("SHIPGUARD_", "GIT_CONFIG_")) or any(
            marker in upper_name
            for marker in ("TOKEN", "SECRET", "PRIVATE_KEY", "PASSWORD", "API_KEY")
        ):
            continue
        if name in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}:
            environment[name] = value
    return environment


def _clone_and_run(
    event: PullRequestEvent,
    installation_token: str,
) -> tuple[Report, int]:
    repository = event.repository.full_name
    if not _REPOSITORY.fullmatch(repository):
        raise WebhookError("Webhook repository name is invalid")
    head_sha = event.pull_request.head.sha
    base_sha = event.pull_request.base.sha
    if not _SHA.fullmatch(head_sha) or not _SHA.fullmatch(base_sha):
        raise WebhookError("Webhook contains an invalid commit SHA")

    with tempfile.TemporaryDirectory(prefix="shipguard-webhook-") as directory:
        root = Path(directory)
        checkout = root / "head"
        trusted_checkout = root / "base"
        environment = _git_environment(installation_token, root)
        remote = f"https://github.com/{repository}.git"
        _run_git(
            [
                "clone",
                "--no-checkout",
                "--depth=1",
                "--filter=blob:none",
                remote,
                str(checkout),
            ],
            cwd=root,
            environment=environment,
        )
        _run_git(
            [
                "-C",
                str(checkout),
                "fetch",
                "--depth=1",
                "origin",
                f"refs/pull/{event.pull_request.number}/head",
            ],
            cwd=root,
            environment=environment,
        )
        fetched_sha = _run_git(
            ["-C", str(checkout), "rev-parse", "FETCH_HEAD"],
            cwd=root,
            environment=environment,
        )
        if fetched_sha.lower() != head_sha.lower():
            raise WebhookError("Fetched pull-request SHA does not match the webhook")
        _run_git(
            ["-C", str(checkout), "checkout", "--detach", head_sha],
            cwd=root,
            environment=environment,
        )
        _run_git(
            ["-C", str(checkout), "fetch", "--depth=1", "origin", base_sha],
            cwd=root,
            environment=environment,
        )
        _run_git(
            [
                "-C",
                str(checkout),
                "worktree",
                "add",
                "--detach",
                str(trusted_checkout),
                base_sha,
            ],
            cwd=root,
            environment=environment,
        )

        config_path = trusted_checkout / ".shipguard.yml"
        try:
            settings: Config = load_config(config_path)
        except ValueError as exc:
            raise WebhookError(f"Trusted base configuration is invalid: {exc}") from exc
        policy_path = settings.policy.get("path", "policies")
        if not isinstance(policy_path, str):
            raise WebhookError("Trusted policy path must be a string")
        configured_policy_path = Path(policy_path)
        if configured_policy_path.is_absolute() or ".." in configured_policy_path.parts:
            raise WebhookError("Trusted policy path must stay inside the base checkout")
        if not configured_policy_path.is_absolute():
            configured_policy_path = config_path.parent / configured_policy_path
        if settings.policy.get("enabled", False) and not configured_policy_path.is_dir():
            raise WebhookError(
                f"Trusted policy directory does not exist: {configured_policy_path}"
            )

        environment_for_cli = _safe_cli_environment()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "shipguard",
                    "check",
                    "--repo",
                    str(checkout),
                    "--config",
                    str(config_path),
                    "--base-ref",
                    base_sha,
                    "--head-ref",
                    head_sha,
                    "--format",
                    "json",
                ],
                cwd=Path(sys.prefix),
                env=environment_for_cli,
                capture_output=True,
                text=True,
                check=False,
                timeout=900,
            )
        except FileNotFoundError as exc:
            raise WebhookError("Python is unavailable on the webhook runner") from exc
        except subprocess.TimeoutExpired as exc:
            raise WebhookError("ShipGuard checks exceeded their timeout") from exc
        try:
            report = Report.model_validate_json(result.stdout)
        except ValidationError as exc:
            detail = result.stderr.strip() or "ShipGuard returned invalid JSON"
            raise WebhookError(f"Unable to read ShipGuard report: {detail[:1000]}") from exc
        return report, result.returncode


def _annotations(report: Report) -> list[dict[str, Any]]:
    annotations = []
    for finding in report.findings:
        if not finding.file or finding.line is None:
            continue
        level = (
            "failure"
            if finding.severity.rank >= Severity.HIGH.rank
            else "warning"
            if finding.severity.rank >= Severity.MEDIUM.rank
            else "notice"
        )
        annotations.append(
            {
                "path": finding.file.replace("\\", "/"),
                "start_line": finding.line,
                "end_line": finding.end_line or finding.line,
                "annotation_level": level,
                "title": finding.rule_id[:255],
                "message": finding.message[:4000],
            }
        )
    return annotations


def process_pull_request(
    event: PullRequestEvent,
    delivery_id: str,
    settings: WebhookSettings,
) -> None:
    client = GitHubAppClient(settings)
    try:
        installation_token = client.create_installation_token(event.installation.id)
        check_id = client.create_check_run(
            event.repository.full_name,
            event.pull_request.head.sha,
            installation_token,
            delivery_id,
        )
        try:
            report, exit_code = _clone_and_run(event, installation_token)
        except WebhookError as exc:
            client.complete_check_run(
                event.repository.full_name,
                check_id,
                installation_token,
                conclusion="failure",
                title="ShipGuard could not complete checks",
                summary=str(exc),
                annotations=[],
            )
            return

        conclusion = "success" if exit_code == 0 and not report.errors else "failure"
        title = (
            f"ShipGuard passed with {len(report.findings)} finding(s)"
            if conclusion == "success"
            else f"ShipGuard found {len(report.findings)} blocking finding(s)"
        )
        summary_parts = [
            (
                f"ShipGuard reported {len(report.findings)} finding(s) and "
                f"{len(report.errors)} checker error(s)."
            )
        ]
        summary_parts.extend(
            f"- `{finding.rule_id}` {finding.file or ''}"
            f"{':' + str(finding.line) if finding.line is not None else ''}: "
            f"{finding.message}"
            for finding in report.findings
        )
        summary_parts.extend(f"- Error: {error}" for error in report.errors)
        client.complete_check_run(
            event.repository.full_name,
            check_id,
            installation_token,
            conclusion=conclusion,
            title=title,
            summary="\n".join(summary_parts),
            annotations=_annotations(report),
        )
    finally:
        client.close()


EventProcessor = Callable[[PullRequestEvent, str, WebhookSettings], None]


def create_app(
    settings: WebhookSettings | None = None,
    *,
    processor: EventProcessor = process_pull_request,
) -> FastAPI:
    configuration = settings or WebhookSettings.from_environment()
    app = FastAPI(title="ShipGuard GitHub App")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook", status_code=202)
    async def webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        signature: Annotated[
            str | None, Header(alias="X-Hub-Signature-256")
        ] = None,
        event_name: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
        delivery_id: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
    ) -> dict[str, str]:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > configuration.max_payload_bytes:
                    raise HTTPException(status_code=413, detail="Payload is too large")
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="Invalid Content-Length"
                ) from exc
        body = await request.body()
        if len(body) > configuration.max_payload_bytes:
            raise HTTPException(status_code=413, detail="Payload is too large")
        if not _signature_is_valid(configuration.webhook_secret, body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        if event_name != "pull_request":
            return {"status": "ignored"}
        try:
            event = PullRequestEvent.model_validate(json.loads(body))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail="Invalid pull-request payload") from exc
        if event.action not in _SUPPORTED_ACTIONS:
            return {"status": "ignored"}
        if not delivery_id:
            raise HTTPException(status_code=400, detail="Missing GitHub delivery id")
        background_tasks.add_task(processor, event, delivery_id, configuration)
        return {"status": "accepted"}

    return app
