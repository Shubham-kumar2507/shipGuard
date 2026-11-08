from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from shipguard.checkers.process import CheckerExecutionError, run_tool
from shipguard.checkers.registry import register
from shipguard.models import CheckContext, Finding, Severity
from shipguard.policy.facts import collect_repo_facts


def _policy_findings(report_text: str) -> list[Finding]:
    try:
        result = json.loads(report_text)
    except json.JSONDecodeError as exc:
        raise CheckerExecutionError(f"Unable to read OPA report: {exc}") from exc

    results = result.get("result") if isinstance(result, dict) else None
    if not isinstance(results, list):
        raise CheckerExecutionError("OPA returned an invalid evaluation result")
    if not results:
        return []
    expressions = results[0].get("expressions")
    if not isinstance(expressions, list) or not expressions:
        raise CheckerExecutionError("OPA returned no policy expression result")
    violations = expressions[0].get("value")
    if not isinstance(violations, list):
        raise CheckerExecutionError("OPA policy result must be an array")

    findings: list[Finding] = []
    for violation in violations:
        if not isinstance(violation, dict):
            raise CheckerExecutionError("OPA returned an invalid policy violation")
        try:
            severity = Severity(str(violation.get("severity", "high")).lower())
        except ValueError:
            severity = Severity.HIGH
        findings.append(
            Finding(
                rule_id=str(violation.get("rule_id") or "POLICY"),
                source="policy",
                severity=severity,
                message=str(violation.get("message") or "Policy violation"),
                file=str(violation["file"]) if violation.get("file") else None,
                line=int(violation["line"]) if violation.get("line") else None,
                category="policy",
            )
        )
    return findings


@register
class PolicyChecker:
    name = "policy"

    def run(self, ctx: CheckContext) -> list[Finding]:
        configured_path: Any = ctx.options.get("policy_path", "policies")
        policy_path = Path(configured_path)
        if not policy_path.is_absolute():
            policy_path = ctx.repo_path / policy_path
        if not policy_path.is_dir():
            raise CheckerExecutionError(f"Policy directory does not exist: {policy_path}")

        facts = collect_repo_facts(
            ctx.repo_path,
            changed_files=ctx.changed_files,
            base_ref=ctx.base_ref,
            head_ref=ctx.head_ref,
        )
        with tempfile.TemporaryDirectory(prefix="shipguard-opa-") as directory:
            input_path = Path(directory) / "facts.json"
            input_path.write_text(json.dumps(facts), encoding="utf-8")
            result = run_tool(
                "opa",
                [
                    "eval",
                    "--format=json",
                    "--data",
                    str(policy_path),
                    "--input",
                    str(input_path),
                    "data.shipguard.deny",
                ],
                cwd=ctx.repo_path,
            )
            return _policy_findings(result.stdout)
