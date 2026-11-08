from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from shipguard.models import Severity


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    line: int = Field(ge=1)
    severity: Severity
    comment: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)
    category: str = Field(min_length=1, max_length=80)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ReviewFinding] = Field(default_factory=list)


class ReviewSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    model: str = "gpt-4.1-mini"
    min_confidence: float = Field(default=0.75, ge=0, le=1)
    max_tokens_per_pr: int = Field(default=8000, ge=256, le=50000)
    max_completion_tokens_per_file: int = Field(default=1000, ge=128, le=4000)
    max_files_per_pr: int = Field(default=100, ge=1, le=500)


class ReviewResult(BaseModel):
    reviewed_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    posted_comments: int = 0
    reserved_tokens: int = 0
