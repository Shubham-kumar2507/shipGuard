from __future__ import annotations

import subprocess
from pathlib import Path

from shipguard.models import CheckerUnavailable


class CheckerExecutionError(RuntimeError):
    """Raised when an external checker fails unexpectedly."""


def run_tool(
    name: str,
    args: list[str],
    *,
    cwd: Path,
    accepted_exit_codes: frozenset[int] = frozenset({0}),
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [name, *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CheckerUnavailable(f"Required tool {name!r} is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise CheckerExecutionError(
            f"{name} exceeded the {timeout}-second timeout"
        ) from exc

    if result.returncode not in accepted_exit_codes:
        detail = result.stderr.strip() or result.stdout.strip() or "no error output"
        raise CheckerExecutionError(
            f"{name} exited with status {result.returncode}: {detail[:1000]}"
        )
    return result
