from pathlib import Path

import pytest

from shipguard.config import ConfigError, load_config
from shipguard.models import Severity


def test_config_defaults_when_path_is_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / ".shipguard.yml")

    assert config.fail_on is Severity.HIGH
    assert config.ignore_paths == []
    assert config.checkers == {}
    assert config.policy == {}
    assert config.review == {}
    assert config.risk == {}


def test_config_loads_yaml_values(tmp_path: Path) -> None:
    config_path = tmp_path / ".shipguard.yml"
    config_path.write_text(
        "version: 1\n"
        "fail_on: critical\n"
        "ignore_paths: ['dist/**']\n"
        "checkers:\n"
        "  secrets:\n"
        "    enabled: true\n"
        "policy:\n"
        "  enabled: true\n"
        "  path: rules\n"
        "review:\n"
        "  min_confidence: 0.6\n"
        "risk:\n"
        "  auto_deploy_below: 35\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.fail_on is Severity.CRITICAL
    assert config.ignore_paths == ["dist/**"]
    assert config.checkers["secrets"]["enabled"] is True
    assert config.policy == {"enabled": True, "path": "rules"}
    assert config.review["min_confidence"] == 0.6
    assert config.risk["auto_deploy_below"] == 35


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("fail_on: severe\n", "Invalid configuration"),
        ("- not-a-mapping\n", "expected a YAML mapping"),
        ("fail_on: [\n", "Unable to read configuration"),
        ("unknown_key: true\n", "Invalid configuration"),
    ],
)
def test_config_invalid_content_raises_clear_error(
    tmp_path: Path, content: str, message: str
) -> None:
    config_path = tmp_path / ".shipguard.yml"
    config_path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_config(config_path)


def test_config_directory_path_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Unable to read configuration"):
        load_config(tmp_path)


def test_none_path_returns_defaults() -> None:
    assert load_config(None) == load_config(Path("missing-shipguard-config.yml"))
