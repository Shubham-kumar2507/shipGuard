from __future__ import annotations

import importlib
import pkgutil

from shipguard.config import Config
from shipguard.models import Checker

_CHECKERS: dict[str, type[Checker]] = {}


def register[CheckerType: type[Checker]](checker_class: CheckerType) -> CheckerType:
    """Register a checker class by its declared name."""
    name = getattr(checker_class, "name", None)
    if not isinstance(name, str) or not name:
        raise ValueError("A registered checker must declare a non-empty name")

    registered = _CHECKERS.get(name)
    if registered is not None and registered is not checker_class:
        raise ValueError(f"A checker named {name!r} is already registered")
    _CHECKERS[name] = checker_class
    return checker_class


def _import_checker_modules() -> None:
    package = importlib.import_module("shipguard.checkers")
    for module in pkgutil.iter_modules(package.__path__):
        if module.name != "registry":
            importlib.import_module(f"{package.__name__}.{module.name}")


def get_checkers(
    config: Config, *, enabled_by_default: frozenset[str] = frozenset()
) -> list[Checker]:
    """Import checker plug-ins and instantiate those enabled by configuration."""
    _import_checker_modules()
    enabled = [
        checker_class
        for name, checker_class in _CHECKERS.items()
        if config.checkers.get(name, {}).get(
            "enabled", name in enabled_by_default
        )
    ]
    return [checker_class() for checker_class in enabled]
