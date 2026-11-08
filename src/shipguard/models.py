from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }[self]


class Finding(BaseModel):
    rule_id: str
    source: str
    severity: Severity
    message: str
    file: str | None = None
    line: int | None = None
    end_line: int | None = None
    category: str | None = None
    confidence: float | None = None
    suggestion: str | None = None


class Report(BaseModel):
    schema_version: str = "1"
    head_sha: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def blocking(self, fail_on: Severity) -> list[Finding]:
        return [
            finding
            for finding in self.findings
            if finding.severity.rank >= fail_on.rank
        ]

    def merge(self, other: Report) -> Report:
        return Report(
            schema_version=self.schema_version,
            head_sha=other.head_sha or self.head_sha,
            findings=[*self.findings, *other.findings],
            errors=[*self.errors, *other.errors],
        )


class CheckerUnavailable(Exception):
    """Raised when an external checker dependency is not installed."""


class CheckContext(BaseModel):
    repo_path: Path
    base_ref: str | None = None
    head_ref: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class Checker(Protocol):
    name: str

    def run(self, ctx: CheckContext) -> list[Finding]: ...
