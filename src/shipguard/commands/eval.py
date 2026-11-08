from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from shipguard.evaluation import (
    EvaluationError,
    load_dataset,
    load_predictions,
    record_score,
    score_predictions,
)


def register(app: typer.Typer) -> None:
    @app.command()
    def eval(
        results: Annotated[
            Path,
            typer.Option(
                "--results",
                help="JSON file containing findings with case_id, file, line, and category.",
                exists=True,
                dir_okay=False,
            ),
        ],
        prompt_version: Annotated[
            str,
            typer.Option("--prompt-version", help="Prompt version to record."),
        ],
        dataset: Annotated[
            Path,
            typer.Option(
                "--dataset",
                help="Labeled evaluation dataset.",
                exists=True,
                dir_okay=False,
            ),
        ] = Path("eval/dataset.json"),
        scores: Annotated[
            Path,
            typer.Option("--scores", help="CSV score history."),
        ] = Path("eval/scores.csv"),
    ) -> None:
        try:
            data = load_dataset(dataset)
            predictions = load_predictions(results)
            summary = score_predictions(
                data, predictions, prompt_version=prompt_version
            )
            record_score(scores, summary)
        except EvaluationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        typer.echo(summary.model_dump_json(indent=2))
