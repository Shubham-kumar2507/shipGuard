from types import ModuleType, SimpleNamespace

from shipguard.checkers import registry
from shipguard.config import Config
from shipguard.models import CheckContext, Finding


def test_registry_discovers_and_filters_enabled_checkers(monkeypatch) -> None:
    class DummyChecker:
        name = "dummy"

        def run(self, ctx: CheckContext) -> list[Finding]:
            return []

    dummy_module = ModuleType("shipguard.checkers.dummy")
    discovered_modules = [SimpleNamespace(name="dummy")]
    original_import_module = registry.importlib.import_module

    monkeypatch.setattr(registry, "_CHECKERS", {})

    def import_module(name: str):
        if name == "shipguard.checkers.dummy":
            registry.register(DummyChecker)
            return dummy_module
        return original_import_module(name)

    monkeypatch.setattr(registry.pkgutil, "iter_modules", lambda _path: discovered_modules)
    monkeypatch.setattr(registry.importlib, "import_module", import_module)

    enabled = registry.get_checkers(Config(checkers={"dummy": {"enabled": True}}))
    disabled = registry.get_checkers(Config(checkers={"dummy": {"enabled": False}}))

    assert isinstance(enabled[0], DummyChecker)
    assert disabled == []
