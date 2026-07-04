"""Smoke tests — proves the package imports and CLI wires up."""

from typer.testing import CliRunner

from deja import __version__
from deja.cli import app


runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_all_planned_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("seed", "start", "chat", "memify", "forget", "ui", "capture", "doctor"):
        assert cmd in result.stdout
