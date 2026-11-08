from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from shipguard.checkers.process import CheckerExecutionError, run_tool
from shipguard.config import ConfigError, load_config
from shipguard.risk import RiskSettings, calculate_risk


def _diff_stats(repo: Path, base_ref: str, head_ref: str) -> tuple[int, int]:
    result = run_tool(
        "git",
        ["diff", "--numstat", f"{base_ref}...{head_ref}"],
        cwd=repo,
    )
    diff_lines = 0
    files_touched = 0
    for line in result.stdout.splitlines():
        fields = line.split("\t", maxsplit=2)
        if len(fields) != 3:
            raise CheckerExecutionError("Git returned malformed diff statistics")
        files_touched += 1
        for value in fields[:2]:
            if value != "-":
                try:
                    diff_lines += int(value)
                except ValueError as exc:
                    raise CheckerExecutionError(
                        "Git returned malformed line counts"
                    ) from exc
    return diff_lines, files_touched


def register(app: typer.Typer) -> None:
    @app.command()
    def risk(
        repo: Annotated[
            Path,
            typer.Option(
                "--repo",
                help="Repository directory to inspect.",
                file_okay=False,
                dir_okay=True,
            ),
        ] = Path("."),
        base_ref: Annotated[
            str,
            typer.Option("--base-ref", help="Base Git ref."),
        ] = ...,
        head_ref: Annotated[
            str,
            typer.Option("--head-ref", help="Head Git ref."),
        ] = "HEAD",
        coverage_before: Annotated[
            float | None,
            typer.Option("--coverage-before", min=0, max=100),
        ] = None,
        coverage_after: Annotated[
            float | None,
            typer.Option("--coverage-after", min=0, max=100),
        ] = None,
        config: Annotated[
            Path | None,
            typer.Option("--config", help="ShipGuard YAML configuration."),
        ] = None,
    ) -> None:
        repo_path = repo.expanduser().resolve()
        if not repo_path.is_dir():
            typer.echo(f"Repository directory does not exist: {repo_path}", err=True)
            raise typer.Exit(code=2)
        config_path = (config or repo_path / ".shipguard.yml").expanduser().resolve()
        try:
            settings = RiskSettings.model_validate(load_config(config_path).risk)
        except (ConfigError, ValidationError) as exc:
            typer.echo(f"Invalid risk configuration: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        try:
            diff_lines, files_touched = _diff_stats(repo_path, base_ref, head_ref)
            report = calculate_risk(
                diff_lines=diff_lines,
                files_touched=files_touched,
                coverage_before=coverage_before,
                coverage_after=coverage_after,
                settings=settings,
            )
        except (CheckerExecutionError, ValueError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc

        log_path = Path(settings.log_path)
        if not log_path.is_absolute():
            log_path = repo_path / log_path
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "base_ref": base_ref,
                            "head_ref": head_ref,
                            **report.model_dump(),
                        }
                    )
                    + "\n"
                )
        except OSError as exc:
            typer.echo(f"Unable to write risk log {log_path}: {exc}", err=True)
            raise typer.Exit(code=2) from exc
        typer.echo(report.model_dump_json(indent=2))
