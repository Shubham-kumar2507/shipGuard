import csv
import json
from pathlib import Path

import pytest

from shipguard.evaluation import (
    EvalDataset,
    EvalPrediction,
    EvaluationError,
    load_dataset,
    record_score,
    score_predictions,
)

ROOT = Path(__file__).parents[2]


def test_benchmark_has_thirty_labeled_cases_and_clean_pull_requests() -> None:
    dataset = load_dataset(ROOT / "eval" / "dataset.json")
    clean_cases = [case for case in dataset.cases if not case.expected]

    assert len(dataset.cases) == 30
    assert len(clean_cases) == 10
    assert all(case.diff for case in dataset.cases)
    assert any("FAKE_SECRET_PLACEHOLDER" in case.diff for case in dataset.cases)


def test_scorer_checks_file_line_category_and_clean_false_positives() -> None:
    dataset = EvalDataset.model_validate(
        {
            "line_tolerance": 2,
            "cases": [
                {
                    "id": "bug",
                    "file": "src/a.py",
                    "diff": "patch",
                    "expected": [
                        {
                            "file": "src/a.py",
                            "line_start": 10,
                            "line_end": 10,
                            "category": "sql-injection",
                        }
                    ],
                },
                {
                    "id": "clean",
                    "file": "src/b.py",
                    "diff": "patch",
                    "expected": [],
                },
            ],
        }
    )
    predictions = [
        EvalPrediction(
            case_id="bug",
            file="src/a.py",
            line=12,
            category="sql-injection",
        ),
        EvalPrediction(
            case_id="bug",
            file="src/a.py",
            line=10,
            category="wrong-category",
        ),
        EvalPrediction(
            case_id="clean",
            file="src/b.py",
            line=4,
            category="style",
        ),
    ]

    summary = score_predictions(
        dataset, predictions, prompt_version="prompt-v1"
    )

    assert summary.true_positives == 1
    assert summary.false_positives == 2
    assert summary.false_negatives == 0
    assert summary.precision == pytest.approx(1 / 3)
    assert summary.recall == 1
    assert summary.clean_pr_count == 1
    assert summary.false_positives_per_clean_pr == 1


def test_unknown_prediction_case_is_rejected() -> None:
    dataset = EvalDataset.model_validate(
        {"cases": [{"id": "known", "file": "a.py", "diff": "patch"}]}
    )
    prediction = EvalPrediction(
        case_id="unknown",
        file="a.py",
        line=1,
        category="bug",
    )

    with pytest.raises(EvaluationError, match="unknown case ids"):
        score_predictions(dataset, [prediction], prompt_version="v1")


def test_score_history_replaces_a_prompt_version(tmp_path: Path) -> None:
    dataset = EvalDataset.model_validate(
        {"cases": [{"id": "clean", "file": "a.py", "diff": "patch"}]}
    )
    score_file = tmp_path / "scores.csv"
    first = score_predictions(dataset, [], prompt_version="v1")
    record_score(score_file, first)

    second = score_predictions(
        dataset,
        [
            EvalPrediction(
                case_id="clean", file="a.py", line=1, category="bug"
            )
        ],
        prompt_version="v1",
    )
    record_score(score_file, second)

    with score_file.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["false_positives"] == "1"


def test_eval_cli_scores_predictions_and_records_prompt_version(
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    from shipguard.cli import main

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "clean",
                        "file": "src/a.py",
                        "diff": "@@ -1 +1 @@\n+value = 1\n",
                        "expected": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "case_id": "clean",
                        "file": "src/a.py",
                        "line": 1,
                        "category": "style",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    scores_path = tmp_path / "scores.csv"

    result = CliRunner().invoke(
        main,
        [
            "eval",
            "--dataset",
            str(dataset_path),
            "--results",
            str(results_path),
            "--scores",
            str(scores_path),
            "--prompt-version",
            "p1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["false_positives_per_clean_pr"] == 1
    assert scores_path.is_file()
