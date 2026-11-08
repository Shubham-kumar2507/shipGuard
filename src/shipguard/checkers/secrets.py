from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from shipguard.checkers.process import CheckerExecutionError, run_tool
from shipguard.checkers.registry import register
from shipguard.models import CheckContext, Finding, Severity


def _read_report(path: Path) -> list[dict[str, Any]]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckerExecutionError(f"Unable to read gitleaks report: {exc}") from exc
    if not isinstance(report, list):
        raise CheckerExecutionError("gitleaks returned an invalid JSON report")
    return [item for item in report if isinstance(item, dict)]


@register
class SecretsChecker:
    name = "secrets"
    enabled_by_default = True

    def run(self, ctx: CheckContext) -> list[Finding]:
        with tempfile.TemporaryDirectory(prefix="shipguard-gitleaks-") as directory:
            report_path = Path(directory) / "report.json"
            run_tool(
                "gitleaks",
                [
                    "dir",
                    str(ctx.repo_path),
                    "--report-format",
                    "json",
                    "--report-path",
                    str(report_path),
                ],
                cwd=ctx.repo_path,
                accepted_exit_codes=frozenset({0, 1}),
            )
            leaks = _read_report(report_path)

        return [
            Finding(
                rule_id=str(leak.get("RuleID") or "GITLEAKS"),
                source=self.name,
                severity=Severity.HIGH,
                message=str(leak.get("Description") or "Potential secret detected"),
                file=str(leak["File"]) if leak.get("File") else None,
                line=int(leak["StartLine"]) if leak.get("StartLine") else None,
                category="secret",
            )
            for leak in leaks
        ]
