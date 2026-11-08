from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from shipguard.checkers.process import CheckerExecutionError, run_tool
from shipguard.checkers.registry import register
from shipguard.models import CheckContext, Finding, Severity


def _severity(value: Any) -> Severity:
    try:
        return Severity(str(value).lower())
    except ValueError:
        return Severity.MEDIUM


def _read_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckerExecutionError(f"Unable to read Trivy report: {exc}") from exc
    if not isinstance(report, dict):
        raise CheckerExecutionError("Trivy returned an invalid JSON report")
    return report


@register
class VulnerabilitiesChecker:
    name = "vulnerabilities"
    enabled_by_default = True

    def run(self, ctx: CheckContext) -> list[Finding]:
        with tempfile.TemporaryDirectory(prefix="shipguard-trivy-") as directory:
            report_path = Path(directory) / "report.json"
            run_tool(
                "trivy",
                [
                    "fs",
                    "--scanners",
                    "vuln,misconfig",
                    "--format",
                    "json",
                    "--output",
                    str(report_path),
                    str(ctx.repo_path),
                ],
                cwd=ctx.repo_path,
            )
            report = _read_report(report_path)

        findings: list[Finding] = []
        results = report.get("Results", [])
        if not isinstance(results, list):
            raise CheckerExecutionError("Trivy report has an invalid Results field")

        for result in results:
            if not isinstance(result, dict):
                continue
            target = str(result.get("Target") or "")
            vulnerabilities = result.get("Vulnerabilities") or []
            if isinstance(vulnerabilities, list):
                for vulnerability in vulnerabilities:
                    if not isinstance(vulnerability, dict):
                        continue
                    vulnerability_id = str(
                        vulnerability.get("VulnerabilityID") or "TRIVY-VULN"
                    )
                    package = str(vulnerability.get("PkgName") or "dependency")
                    fixed = vulnerability.get("FixedVersion")
                    message = f"{package}: {vulnerability_id}"
                    if fixed:
                        message += f" (fixed in {fixed})"
                    findings.append(
                        Finding(
                            rule_id=vulnerability_id,
                            source=self.name,
                            severity=_severity(vulnerability.get("Severity")),
                            message=message,
                            file=target or None,
                            category="vulnerability",
                        )
                    )

            misconfigurations = result.get("Misconfigurations") or []
            if isinstance(misconfigurations, list):
                for misconfiguration in misconfigurations:
                    if not isinstance(misconfiguration, dict):
                        continue
                    cause = misconfiguration.get("CauseMetadata") or {}
                    if not isinstance(cause, dict):
                        cause = {}
                    finding_id = str(misconfiguration.get("ID") or "TRIVY-MISCONFIG")
                    title = str(
                        misconfiguration.get("Title")
                        or misconfiguration.get("Description")
                        or finding_id
                    )
                    findings.append(
                        Finding(
                            rule_id=finding_id,
                            source=self.name,
                            severity=_severity(misconfiguration.get("Severity")),
                            message=title,
                            file=target or None,
                            line=(
                                int(cause["StartLine"])
                                if cause.get("StartLine")
                                else None
                            ),
                            category="misconfiguration",
                        )
                    )
        return findings
