from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from shipguard.checkers.process import CheckerExecutionError
from shipguard.checkers.registry import get_checkers
from shipguard.config import ConfigError, load_config
from shipguard.models import CheckContext, CheckerUnavailable, Report, Severity


def register(app: typer.Typer) -> None:
    @app.command()
    def check(
        repo: Annotated[
            Path,
            typer.Option(
                "--repo",
                help="Repository directory to check.",
                file_okay=False,
                dir_okay=True,
            ),
        ] = Path("."),
        config: Annotated[
            Path | None,
            typer.Option(
                "--config",
                help="ShipGuard YAML configuration (defaults to REPO/.shipguard.yml).",
            ),
        ] = None,
        output_format: Annotated[
            Literal["text", "json"],
            typer.Option("--format", help="Report format."),
        ] = "text",
        fail_on: Annotated[
            Severity | None,
            typer.Option("--fail-on", help="Override the configured blocking threshold."),
        ] = None,
        base_ref: Annotated[
            str | None,
            typer.Option("--base-ref", help="Base Git ref for changed-file policies."),
        ] = None,
        head_ref: Annotated[
            str | None,
            typer.Option("--head-ref", help="Head Git ref (defaults to HEAD)."),
        ] = None,
    ) -> None:
        repo_path = repo.expanduser().resolve()
        if not repo_path.is_dir():
            typer.echo(f"Repository directory does not exist: {repo_path}", err=True)
            raise typer.Exit(code=2)

        config_path = (config or repo_path / ".shipguard.yml").expanduser().resolve()
        try:
            settings = load_config(config_path)
        except ConfigError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc

        checker_config = dict(settings.checkers)
        if settings.policy.get("enabled", False) and "policy" not in checker_config:
            checker_config["policy"] = {"enabled": True}
            settings = settings.model_copy(update={"checkers": checker_config})
        checkers = get_checkers(
            settings,
            enabled_by_default=frozenset(
                {"secrets", "vulnerabilities", "sbom", "pinning"}
            ),
        )
        sbom_settings = settings.checkers.get("sbom", {})
        configured_policy_path = settings.policy.get("path", "policies")
        sbom_path = sbom_settings.get("output", "shipguard-sbom.cdx.json")
        if not isinstance(configured_policy_path, str) or not isinstance(sbom_path, str):
            typer.echo("Policy path and SBOM output must be strings", err=True)
            raise typer.Exit(code=2)
        policy_path = Path(configured_policy_path)
        if not policy_path.is_absolute():
            policy_path = config_path.parent / policy_path
        context = CheckContext(
            repo_path=repo_path,
            base_ref=base_ref,
            head_ref=head_ref,
            options={
                "sbom_path": sbom_path,
                "sbom_excludes": sbom_settings.get(
                    "exclude",
                    [
                        ".git/**",
                        ".venv/**",
                        "venv/**",
                        "__pycache__/**",
                        ".pytest_cache/**",
                    ],
                ),
                "policy_path": policy_path,
            },
        )
        report = Report()
        for checker in checkers:
            try:
                report.findings.extend(checker.run(context))
            except (CheckerUnavailable, CheckerExecutionError) as exc:
                report.errors.append(f"{checker.name}: {exc}")

        if output_format == "json":
            typer.echo(report.model_dump_json(indent=2))
        else:
            _print_text_report(report)

        threshold = fail_on or settings.fail_on
        if report.errors or report.blocking(threshold):
            raise typer.Exit(code=1)


def _print_text_report(report: Report) -> None:
    if report.findings:
        typer.echo("ShipGuard findings:")
        for finding in report.findings:
            location = finding.file or "<repository>"
            if finding.line is not None:
                location += f":{finding.line}"
            typer.echo(
                f"[{finding.severity.value.upper():8}] {finding.rule_id} "
                f"{location} - {finding.message}"
            )
    else:
        typer.echo("No findings.")

    for error in report.errors:
        typer.echo(f"ERROR: {error}")
    typer.echo(
        f"{len(report.findings)} finding(s), {len(report.errors)} checker error(s)"
    )
