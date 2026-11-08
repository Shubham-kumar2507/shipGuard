from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from shipguard.config import ConfigError, load_config
from shipguard.review.github import GitHubClient, ReviewError
from shipguard.review.llm import OpenAIReviewer
from shipguard.review.models import ReviewSettings
from shipguard.review.service import PullRequestReviewer


def register(app: typer.Typer) -> None:
    @app.command()
    def review(
        repository: Annotated[
            str,
            typer.Option(
                "--repository",
                help="GitHub repository in OWNER/NAME format.",
            ),
        ],
        pull_request: Annotated[
            int,
            typer.Option("--pull-request", min=1, help="Pull request number."),
        ],
        config: Annotated[
            Path | None,
            typer.Option("--config", help="ShipGuard YAML configuration."),
        ] = None,
    ) -> None:
        owner, separator, repo_name = repository.partition("/")
        if not separator or not owner or not repo_name or "/" in repo_name:
            typer.echo("--repository must be in OWNER/NAME format", err=True)
            raise typer.Exit(code=2)

        github_token = os.environ.get("GITHUB_TOKEN")
        llm_api_key = os.environ.get("SHIPGUARD_LLM_API_KEY")
        if not github_token or not llm_api_key:
            typer.echo(
                "GITHUB_TOKEN and SHIPGUARD_LLM_API_KEY must be set in the environment",
                err=True,
            )
            raise typer.Exit(code=2)

        try:
            settings = ReviewSettings.model_validate(
                load_config(config or Path(".shipguard.yml")).review
            )
        except (ConfigError, ValidationError) as exc:
            typer.echo(f"Invalid review configuration: {exc}", err=True)
            raise typer.Exit(code=2) from exc
        if not settings.enabled:
            typer.echo("LLM review is disabled by configuration.")
            raise typer.Exit(code=0)

        github = GitHubClient(github_token)
        llm = OpenAIReviewer(llm_api_key, settings.model)
        try:
            result = PullRequestReviewer(github, llm, settings).review(
                owner, repo_name, pull_request
            )
        except ReviewError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        finally:
            github.close()
            llm.close()

        typer.echo(
            f"Reviewed {len(result.reviewed_files)} file(s), posted "
            f"{result.posted_comments} comment(s); skipped "
            f"{len(result.skipped_files)} file(s); reserved "
            f"{result.reserved_tokens} token(s)."
        )
