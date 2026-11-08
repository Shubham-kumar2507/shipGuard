from __future__ import annotations

from pathlib import Path

from shipguard.checkers.process import CheckerExecutionError, run_tool
from shipguard.checkers.registry import register
from shipguard.models import CheckContext, Finding


@register
class SbomChecker:
    name = "sbom"
    enabled_by_default = True

    def run(self, ctx: CheckContext) -> list[Finding]:
        configured_path = ctx.options.get("sbom_path", "shipguard-sbom.cdx.json")
        output_path = Path(configured_path)
        if not output_path.is_absolute():
            output_path = ctx.repo_path / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        excludes = ctx.options.get(
            "sbom_excludes",
            [".git/**", ".venv/**", "venv/**", "__pycache__/**", ".pytest_cache/**"],
        )
        if not isinstance(excludes, list) or not all(
            isinstance(pattern, str) for pattern in excludes
        ):
            raise CheckerExecutionError("SBOM exclusions must be a list of strings")
        args = [
            f"dir:{ctx.repo_path}",
            "--output",
            f"cyclonedx-json={output_path}",
            "--quiet",
        ]
        for pattern in excludes:
            args.extend(["--exclude", pattern])

        run_tool(
            "syft",
            args,
            cwd=ctx.repo_path,
        )
        if not output_path.is_file():
            raise CheckerExecutionError(
                f"Syft completed without creating the SBOM at {output_path}"
            )
        return []
