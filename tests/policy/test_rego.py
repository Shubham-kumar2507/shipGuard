import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
POLICY_DIRECTORY = ROOT / "policies"


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("opa") is None, reason="OPA is not installed")
def test_opa_policy_unit_tests_pass() -> None:
    result = subprocess.run(
        ["opa", "test", str(POLICY_DIRECTORY), "--verbose"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
