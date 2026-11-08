import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from shipguard.checkers.pinning import PinningChecker
from shipguard.checkers.process import CheckerExecutionError, run_tool
from shipguard.checkers.sbom import SbomChecker
from shipguard.checkers.secrets import SecretsChecker
from shipguard.checkers.vulnerabilities import VulnerabilitiesChecker
from shipguard.models import CheckContext, Severity


def test_gitleaks_report_becomes_secret_findings(
    tmp_path: Path, monkeypatch
) -> None:
    report = [
        {
            "RuleID": "aws-access-key",
            "Description": "AWS access key detected",
            "File": "config.txt",
            "StartLine": 1,
        }
    ]

    def run(command, **_kwargs):
        report_path = Path(command[command.index("--report-path") + 1])
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)

    findings = SecretsChecker().run(CheckContext(repo_path=tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "aws-access-key"
    assert findings[0].severity is Severity.HIGH
    assert findings[0].file == "config.txt"
    assert findings[0].line == 1


def test_trivy_report_maps_vulnerabilities_and_misconfigurations(
    tmp_path: Path, monkeypatch
) -> None:
    report = {
        "Results": [
            {
                "Target": "requirements.txt",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2025-0001",
                        "PkgName": "example",
                        "Severity": "CRITICAL",
                        "FixedVersion": "2.0.0",
                    }
                ],
                "Misconfigurations": [
                    {
                        "ID": "AVD-TEST-0001",
                        "Title": "Container runs as root",
                        "Severity": "HIGH",
                        "CauseMetadata": {"StartLine": 8},
                    }
                ],
            }
        ]
    }

    def run(command, **_kwargs):
        report_path = Path(command[command.index("--output") + 1])
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)

    findings = VulnerabilitiesChecker().run(CheckContext(repo_path=tmp_path))

    assert [finding.rule_id for finding in findings] == [
        "CVE-2025-0001",
        "AVD-TEST-0001",
    ]
    assert findings[0].severity is Severity.CRITICAL
    assert findings[1].line == 8
    assert findings[1].category == "misconfiguration"


def test_syft_writes_cyclonedx_sbom(tmp_path: Path, monkeypatch) -> None:
    def run(command, **_kwargs):
        output_argument = next(arg for arg in command if arg.startswith("cyclonedx-json="))
        output_path = Path(output_argument.removeprefix("cyclonedx-json="))
        output_path.write_text('{"bomFormat":"CycloneDX"}', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)

    findings = SbomChecker().run(CheckContext(repo_path=tmp_path))

    assert findings == []
    assert (tmp_path / "shipguard-sbom.cdx.json").is_file()


def test_pinning_checker_reports_unpinned_packages_and_actions(
    tmp_path: Path,
) -> None:
    (tmp_path / "requirements.txt").write_text(
        "fastapi>=0.110\nhttpx==0.28.1\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["typer>=0.12", "pydantic==2.0"]\n',
        encoding="utf-8",
    )
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "steps:\n"
        "  - uses: actions/checkout@v4\n"
        "  - uses: owner/action@0123456789abcdef0123456789abcdef01234567\n",
        encoding="utf-8",
    )

    findings = PinningChecker().run(CheckContext(repo_path=tmp_path))

    assert [(finding.rule_id, finding.file, finding.line) for finding in findings] == [
        ("PIN-DEPENDENCY", "requirements.txt", 1),
        ("PIN-DEPENDENCY", "pyproject.toml", 2),
        ("PIN-GITHUB-ACTION", ".github/workflows/ci.yml", 2),
    ]


def test_tool_errors_are_reported_with_stderr(tmp_path: Path, monkeypatch) -> None:
    def run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["trivy"], returncode=2, stdout="", stderr="database unavailable"
        )

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)

    try:
        run_tool("trivy", ["fs", str(tmp_path)], cwd=tmp_path)
    except CheckerExecutionError as exc:
        assert "database unavailable" in str(exc)
    else:
        raise AssertionError("CheckerExecutionError was not raised")
