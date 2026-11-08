from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from shipguard.checkers.process import CheckerExecutionError
from shipguard.policy.facts import collect_repo_facts


def register(app: typer.Typer) -> None:
    @app.command()
    def facts(
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
            str | None,
            typer.Option("--base-ref", help="Base Git ref for changed-file facts."),
        ] = None,
        head_ref: Annotated[
            str | None,
            typer.Option("--head-ref", help="Head Git ref (defaults to HEAD)."),
        ] = None,
    ) -> None:
        repo_path = repo.expanduser().resolve()
        if not repo_path.is_dir():
            typer.echo(f"Repository directory does not exist: {repo_path}", err=True)
            raise typer.Exit(code=2)
        try:
            facts = collect_repo_facts(
                repo_path, base_ref=base_ref, head_ref=head_ref
            )
        except CheckerExecutionError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        typer.echo(json.dumps(facts, indent=2))
