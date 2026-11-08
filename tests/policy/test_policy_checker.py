import json
import subprocess
from pathlib import Path

from shipguard.checkers.policy import PolicyChecker
from shipguard.models import CheckContext, Severity


def test_policy_checker_converts_opa_violations_to_findings(
    tmp_path: Path, monkeypatch
) -> None:
    policy_path = tmp_path / "policies"
    policy_path.mkdir()
    (tmp_path / "CODEOWNERS").write_text("* @maintainers\n", encoding="utf-8")
    facts = {
        "dockerfiles": [],
        "changed_files": [],
        "changed_source_files": [],
        "tests_changed": False,
        "codeowners_exists": True,
    }
    output = {"result": [{"expressions": [{"value": [
        {
            "rule_id": "POLICY-NO-LATEST",
            "severity": "high",
            "file": "Dockerfile",
            "message": "latest tag",
        }
    ]}]}]}

    def run(command, **_kwargs):
        input_path = Path(command[command.index("--input") + 1])
        assert json.loads(input_path.read_text(encoding="utf-8")) == facts
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout=json.dumps(output), stderr=""
        )

    monkeypatch.setattr("shipguard.checkers.process.subprocess.run", run)

    findings = PolicyChecker().run(
        CheckContext(repo_path=tmp_path, options={"policy_path": "policies"})
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "POLICY-NO-LATEST"
    assert findings[0].severity is Severity.HIGH
    assert findings[0].file == "Dockerfile"


def test_policy_checker_reports_missing_policy_directory(tmp_path: Path) -> None:
    try:
        PolicyChecker().run(
            CheckContext(repo_path=tmp_path, options={"policy_path": "missing"})
        )
    except RuntimeError as exc:
        assert "Policy directory does not exist" in str(exc)
    else:
        raise AssertionError("A missing policy directory should fail")
