from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    @app.command()
    def webhook(
        host: Annotated[
            str,
            typer.Option("--host", help="Interface to bind the webhook server to."),
        ] = "0.0.0.0",
        port: Annotated[
            int,
            typer.Option("--port", min=1, max=65535, help="Port to bind."),
        ] = 8000,
    ) -> None:
        try:
            import uvicorn

            from shipguard.webhook import (
                WebhookError,
                WebhookSettings,
                create_app,
            )
        except ImportError as exc:
            typer.echo(
                "The webhook server requires the 'app' extra; install shipguard[app].",
                err=True,
            )
            raise typer.Exit(code=2) from exc
        try:
            settings = WebhookSettings.from_environment()
        except WebhookError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        uvicorn.run(create_app(settings), host=host, port=port)
