from __future__ import annotations

import importlib
import pkgutil

import typer

from shipguard import __version__

main = typer.Typer(name="shipguard", help="Gate pull requests with ShipGuard.")


@main.callback()
def _root() -> None:
    """Run ShipGuard commands."""


@main.command()
def version() -> None:
    """Show the installed ShipGuard version."""
    typer.echo(f"ShipGuard {__version__}")


def _register_commands() -> None:
    package = importlib.import_module("shipguard.commands")
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{module_info.name}")
        register = getattr(module, "register", None)
        if register is not None:
            register(main)


_register_commands()
