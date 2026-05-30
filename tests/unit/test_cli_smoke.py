from typer.testing import CliRunner

from hermes_slack_ext.cli import app
from hermes_slack_ext import __version__


def test_version_command():
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
