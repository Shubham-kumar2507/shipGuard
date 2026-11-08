import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).parents[2]
TEMPLATE = REPOSITORY_ROOT / "templates" / "fastapi-service"


@pytest.mark.integration
@pytest.mark.skipif(
    importlib.util.find_spec("copier") is None,
    reason="Copier is not installed",
)
def test_copier_generates_fastapi_service(tmp_path: Path) -> None:
    destination = tmp_path / "generated-service"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "service_name=generated-service",
            "--data",
            "service_description=Generated for testing",
            "--data",
            "maintainer=Test maintainers",
            str(TEMPLATE),
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (destination / "Dockerfile").is_file()
    assert (destination / "app" / "main.py").is_file()
    assert (destination / "tests" / "test_main.py").is_file()
    assert (destination / ".github" / "workflows" / "ci.yml").is_file()
    assert "generated-service" in (destination / "README.md").read_text(
        encoding="utf-8"
    )
    lint_result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=destination,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert lint_result.returncode == 0, lint_result.stdout + lint_result.stderr
    test_result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=destination,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert test_result.returncode == 0, test_result.stdout + test_result.stderr
