from typer.testing import CliRunner

from shipguard import __version__
from shipguard.cli import main


def test_version_command() -> None:
    result = CliRunner().invoke(main, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout
