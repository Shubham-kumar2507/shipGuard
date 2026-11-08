from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from shipguard.checkers.process import CheckerExecutionError
from shipguard.checkers.registry import register
from shipguard.models import CheckContext, Finding, Severity

_REQUIREMENT = re.compile(
    r"^\s*[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?\s*(.*?)\s*$"
)
_ACTION = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)['\"]?")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "dist", "build"}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_pinned(requirement: str) -> bool:
    match = _REQUIREMENT.match(requirement)
    if match is None:
        return False
    specifier = match.group(1).split(";", maxsplit=1)[0].strip()
    if " @ " in requirement:
        return bool(re.search(r"@[0-9a-fA-F]{40}(?:#.*)?$", requirement.strip()))
    return (
        specifier.startswith("==")
        and "," not in specifier
        and "*" not in specifier
        and bool(specifier[2:].strip())
    )


def _dependency_values(data: dict[str, Any]) -> list[str]:
    build_system = data.get("build-system", {})
    project = data.get("project", {})
    dependencies: list[str] = []
    if isinstance(build_system, dict):
        build_dependencies = build_system.get("requires", [])
        if isinstance(build_dependencies, list):
            dependencies.extend(
                item for item in build_dependencies if isinstance(item, str)
            )
    if not isinstance(project, dict):
        return dependencies
    direct = project.get("dependencies", [])
    if isinstance(direct, list):
        dependencies.extend(item for item in direct if isinstance(item, str))
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group in optional.values():
            if isinstance(group, list):
                dependencies.extend(item for item in group if isinstance(item, str))
    return dependencies


def _check_requirements_file(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.split("#", maxsplit=1)[0].strip()
        if not stripped or stripped.startswith(("-", "http://", "https://")):
            continue
        if not _is_pinned(stripped):
            findings.append(
                Finding(
                    rule_id="PIN-DEPENDENCY",
                    source="pinning",
                    severity=Severity.HIGH,
                    message="Dependency is not pinned to an exact version",
                    file=_relative(path, root),
                    line=line_number,
                    category="dependency-pinning",
                )
            )
    return findings


def _check_pyproject(path: Path, root: Path) -> list[Finding]:
    content = path.read_text(encoding="utf-8")
    try:
        dependencies = _dependency_values(tomllib.loads(content))
    except (tomllib.TOMLDecodeError, UnicodeError) as exc:
        raise CheckerExecutionError(f"Unable to parse {_relative(path, root)}: {exc}") from exc

    findings: list[Finding] = []
    lines = content.splitlines()
    search_from = 0
    for dependency in dependencies:
        if _is_pinned(dependency):
            continue
        matching_line = next(
            (
                index
                for index in range(search_from, len(lines))
                if dependency in lines[index]
            ),
            None,
        )
        if matching_line is None:
            matching_line = 0
        else:
            search_from = matching_line + 1
        findings.append(
            Finding(
                rule_id="PIN-DEPENDENCY",
                source="pinning",
                severity=Severity.HIGH,
                message=f"Dependency {dependency!r} is not pinned to an exact version",
                file=_relative(path, root),
                line=matching_line + 1,
                category="dependency-pinning",
            )
        )
    return findings


@register
class PinningChecker:
    name = "pinning"
    enabled_by_default = True

    def run(self, ctx: CheckContext) -> list[Finding]:
        findings: list[Finding] = []
        for path in ctx.repo_path.rglob("requirements*.txt"):
            if not _SKIP_PARTS.intersection(path.parts):
                findings.extend(_check_requirements_file(path, ctx.repo_path))
        pyproject = ctx.repo_path / "pyproject.toml"
        if pyproject.is_file():
            findings.extend(_check_pyproject(pyproject, ctx.repo_path))

        workflows = ctx.repo_path / ".github" / "workflows"
        if workflows.is_dir():
            for path in workflows.rglob("*"):
                if path.suffix.lower() not in {".yml", ".yaml"}:
                    continue
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1
                ):
                    match = _ACTION.match(line)
                    if match is None:
                        continue
                    action = match.group(1)
                    if action.startswith("./"):
                        continue
                    _, separator, reference = action.partition("@")
                    if separator and _SHA.fullmatch(reference):
                        continue
                    findings.append(
                        Finding(
                            rule_id="PIN-GITHUB-ACTION",
                            source=self.name,
                            severity=Severity.HIGH,
                            message=f"GitHub Action {action!r} must be pinned to a full commit SHA",
                            file=_relative(path, ctx.repo_path),
                            line=line_number,
                            category="action-pinning",
                        )
                    )
        return findings
