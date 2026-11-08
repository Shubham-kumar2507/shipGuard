from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diff_weight: float = Field(default=40, ge=0)
    files_weight: float = Field(default=30, ge=0)
    coverage_drop_weight: float = Field(default=30, ge=0)
    max_diff_lines: int = Field(default=500, ge=1)
    max_files: int = Field(default=20, ge=1)
    max_coverage_drop: float = Field(default=20, gt=0)
    log_path: str = ".shipguard-cache/risk.jsonl"

    @model_validator(mode="after")
    def weights_total_at_most_100(self) -> RiskSettings:
        if self.diff_weight + self.files_weight + self.coverage_drop_weight > 100:
            raise ValueError("Risk component weights must sum to at most 100")
        return self


class RiskReport(BaseModel):
    diff_lines: int
    files_touched: int
    coverage_drop: float | None = None
    diff_component: float
    files_component: float
    coverage_component: float
    score: float


def calculate_risk(
    *,
    diff_lines: int,
    files_touched: int,
    coverage_before: float | None,
    coverage_after: float | None,
    settings: RiskSettings,
) -> RiskReport:
    if diff_lines < 0 or files_touched < 0:
        raise ValueError("Diff lines and files touched cannot be negative")
    for coverage in (coverage_before, coverage_after):
        if coverage is not None and not 0 <= coverage <= 100:
            raise ValueError("Coverage must be between 0 and 100")
    if (coverage_before is None) != (coverage_after is None):
        raise ValueError("Both coverage values must be provided together")

    coverage_drop = (
        max(coverage_before - coverage_after, 0)
        if coverage_before is not None and coverage_after is not None
        else None
    )
    diff_component = min(diff_lines / settings.max_diff_lines, 1) * settings.diff_weight
    files_component = min(files_touched / settings.max_files, 1) * settings.files_weight
    coverage_component = (
        min(coverage_drop / settings.max_coverage_drop, 1)
        * settings.coverage_drop_weight
        if coverage_drop is not None
        else 0
    )
    return RiskReport(
        diff_lines=diff_lines,
        files_touched=files_touched,
        coverage_drop=coverage_drop,
        diff_component=round(diff_component, 2),
        files_component=round(files_component, 2),
        coverage_component=round(coverage_component, 2),
        score=round(diff_component + files_component + coverage_component, 2),
    )
