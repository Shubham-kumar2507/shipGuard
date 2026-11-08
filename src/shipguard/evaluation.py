from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class EvaluationError(ValueError):
    """Raised when an evaluation dataset or prediction file is invalid."""


class ExpectedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    category: str


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    file: str
    diff: str
    expected: list[ExpectedFinding] = Field(default_factory=list)


class EvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    line_tolerance: int = Field(default=3, ge=0)
    cases: list[EvalCase]


class EvalPrediction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case_id: str
    file: str
    line: int = Field(ge=1)
    category: str


class EvalSummary(BaseModel):
    prompt_version: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    clean_pr_count: int
    false_positives_per_clean_pr: float


def load_dataset(path: Path) -> EvalDataset:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return EvalDataset.model_validate(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise EvaluationError(f"Unable to load evaluation dataset {path}: {exc}") from exc


def load_predictions(path: Path) -> list[EvalPrediction]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("predictions")
        if not isinstance(data, list):
            raise EvaluationError("Predictions must be a JSON array")
        return [EvalPrediction.model_validate(item) for item in data]
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise EvaluationError(f"Unable to load predictions {path}: {exc}") from exc


def _normalized_path(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def _normalized_category(category: str) -> str:
    return category.strip().lower().replace("_", "-")


def score_predictions(
    dataset: EvalDataset,
    predictions: list[EvalPrediction],
    *,
    prompt_version: str,
) -> EvalSummary:
    cases = {case.id: case for case in dataset.cases}
    unknown_cases = sorted({item.case_id for item in predictions} - cases.keys())
    if unknown_cases:
        raise EvaluationError(
            f"Predictions refer to unknown case ids: {', '.join(unknown_cases)}"
        )

    remaining = {
        case.id: list(case.expected)
        for case in dataset.cases
    }
    true_positives = 0
    false_positives_by_case: dict[str, int] = {}
    for prediction in predictions:
        expected_findings = remaining[prediction.case_id]
        match = next(
            (
                finding
                for finding in expected_findings
                if _normalized_path(prediction.file) == _normalized_path(finding.file)
                and abs(prediction.line - finding.line_start)
                <= dataset.line_tolerance
                and prediction.line
                <= finding.line_end + dataset.line_tolerance
                and _normalized_category(prediction.category)
                == _normalized_category(finding.category)
            ),
            None,
        )
        if match is None:
            false_positives_by_case[prediction.case_id] = (
                false_positives_by_case.get(prediction.case_id, 0) + 1
            )
        else:
            expected_findings.remove(match)
            true_positives += 1

    false_positives = sum(false_positives_by_case.values())
    false_negatives = sum(len(items) for items in remaining.values())
    total_predictions = true_positives + false_positives
    total_expected = true_positives + false_negatives
    clean_cases = [case for case in dataset.cases if not case.expected]
    clean_false_positives = sum(
        false_positives_by_case.get(case.id, 0) for case in clean_cases
    )
    return EvalSummary(
        prompt_version=prompt_version,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=true_positives / total_predictions if total_predictions else 0.0,
        recall=true_positives / total_expected if total_expected else 0.0,
        clean_pr_count=len(clean_cases),
        false_positives_per_clean_pr=(
            clean_false_positives / len(clean_cases) if clean_cases else 0.0
        ),
    )


def record_score(path: Path, summary: EvalSummary) -> None:
    columns = [
        "prompt_version",
        "true_positives",
        "false_positives",
        "false_negatives",
        "precision",
        "recall",
        "clean_pr_count",
        "false_positives_per_clean_pr",
    ]
    rows: dict[str, dict[str, str]] = {}
    if path.exists():
        try:
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames and reader.fieldnames != columns:
                    raise EvaluationError(f"Unexpected score table columns in {path}")
                rows = {
                    row["prompt_version"]: row
                    for row in reader
                    if row.get("prompt_version")
                }
        except OSError as exc:
            raise EvaluationError(f"Unable to read score table {path}: {exc}") from exc

    rows[summary.prompt_version] = {
        name: str(getattr(summary, name)) for name in columns
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows.values())
        os.replace(temporary_path, path)
    except OSError as exc:
        raise EvaluationError(f"Unable to write score table {path}: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
