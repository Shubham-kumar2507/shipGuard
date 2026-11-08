import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from shipguard.cli import main
from shipguard.risk import RiskSettings, calculate_risk


def test_risk_score_weights_diff_files_and_coverage_drop() -> None:
    report = calculate_risk(
        diff_lines=250,
        files_touched=10,
        coverage_before=90,
        coverage_after=80,
        settings=RiskSettings(),
    )

    assert report.diff_component == 20
    assert report.files_component == 15
    assert report.coverage_component == 15
    assert report.coverage_drop == 10
    assert report.score == 50


def test_risk_score_saturates_components_and_ignores_coverage_improvement() -> None:
    report = calculate_risk(
        diff_lines=1000,
        files_touched=30,
        coverage_before=70,
        coverage_after=85,
        settings=RiskSettings(),
    )

    assert report.coverage_drop == 0
    assert report.coverage_component == 0
    assert report.score == 70


def test_risk_settings_reject_weights_over_100() -> None:
    with pytest.raises(ValueError, match="sum to at most 100"):
        RiskSettings(diff_weight=50, files_weight=30, coverage_drop_weight=30)


def test_risk_cli_computes_git_diff_and_appends_jsonl_log(
    tmp_path: Path, monkeypatch
) -> None:
    def run(command, **_kwargs):
        assert command == ["git", "diff", "--numstat", "main...HEAD"]
        return SimpleNamespace(
            returncode=0,
            stdout="10\t5\tsrc/a.py\n-\t-\tassets/image.png\n",
            stderr="",
        )

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)

    result = CliRunner().invoke(
        main,
        [
            "risk",
            "--repo",
            str(tmp_path),
            "--base-ref",
            "main",
            "--coverage-before",
            "90",
            "--coverage-after",
            "85",
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["diff_lines"] == 15
    assert report["files_touched"] == 2
    log = tmp_path / ".shipguard-cache" / "risk.jsonl"
    assert json.loads(log.read_text(encoding="utf-8"))["score"] == report["score"]
