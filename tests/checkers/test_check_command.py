import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from shipguard.checkers.secrets import SecretsChecker
from shipguard.cli import main


def test_check_fails_and_reports_fake_secret_as_json(
    tmp_path: Path, monkeypatch
) -> None:
    fake_key = "AKIA" + "IOSFODNN7EXAMPLE"
    (tmp_path / "credentials.txt").write_text(fake_key, encoding="utf-8")

    def run(command, **_kwargs):
        assert fake_key in (tmp_path / "credentials.txt").read_text(encoding="utf-8")
        report_path = Path(command[command.index("--report-path") + 1])
        report_path.write_text(
            json.dumps(
                [
                    {
                        "RuleID": "aws-access-key",
                        "Description": "AWS access key detected",
                        "File": "credentials.txt",
                        "StartLine": 1,
                    }
                ]
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)
    monkeypatch.setattr(
        "shipguard.commands.check.get_checkers",
        lambda _config, **_kwargs: [SecretsChecker()],
    )

    result = CliRunner().invoke(
        main, ["check", "--repo", str(tmp_path), "--format", "json"]
    )

    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["findings"][0]["rule_id"] == "aws-access-key"
    assert report["findings"][0]["file"] == "credentials.txt"
    assert report["findings"][0]["line"] == 1


def test_check_rejects_missing_repository(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["check", "--repo", str(tmp_path / "missing")])

    assert result.exit_code == 2
    assert "Repository directory does not exist" in result.output
