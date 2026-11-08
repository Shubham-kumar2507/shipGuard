from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shipguard.models import Severity


class ConfigError(ValueError):
    """Raised when ShipGuard configuration is invalid."""


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    fail_on: Severity = Severity.HIGH
    ignore_paths: list[str] = Field(default_factory=list)
    checkers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    review: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)


def load_config(path: Path | None) -> Config:
    """Load a ShipGuard YAML configuration, or return defaults if absent."""
    if path is None or not path.exists():
        return Config()

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Unable to read configuration {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"Invalid configuration {path}: expected a YAML mapping")

    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration {path}: {exc}") from exc
