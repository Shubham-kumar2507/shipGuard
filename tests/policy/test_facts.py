from pathlib import Path

from shipguard.policy.facts import collect_repo_facts


def test_collect_repo_facts_parses_dockerfiles_and_changes(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(
        "FROM python:latest AS builder\nFROM builder AS runtime\nFROM scratch\n",
        encoding="utf-8",
    )
    owners = tmp_path / ".github" / "CODEOWNERS"
    owners.parent.mkdir()
    owners.write_text("* @maintainers\n", encoding="utf-8")

    facts = collect_repo_facts(
        tmp_path,
        changed_files=["src/app.py", "tests/test_app.py", "README.md"],
    )

    assert facts == {
        "dockerfiles": [{"file": "Dockerfile", "tags": ["python:latest"]}],
        "changed_files": ["src/app.py", "tests/test_app.py", "README.md"],
        "changed_source_files": ["src/app.py"],
        "tests_changed": True,
        "codeowners_exists": True,
    }


def test_collect_repo_facts_reads_changed_files_from_git(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class Result:
        stdout = "src/app.py\ntests/test_app.py\n"

    def run_tool(name, args, *, cwd, **_kwargs):
        captured.update(name=name, args=args, cwd=cwd)
        return Result()

    monkeypatch.setattr("shipguard.policy.facts.run_tool", run_tool)

    facts = collect_repo_facts(tmp_path, base_ref="main")

    assert captured["name"] == "git"
    assert captured["args"] == ["diff", "--name-only", "main...HEAD"]
    assert facts["tests_changed"] is True
    assert facts["changed_source_files"] == ["src/app.py"]
