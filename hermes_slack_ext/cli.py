from __future__ import annotations

import typer

from hermes_slack_ext import __version__

app = typer.Typer(
    add_completion=False,
    help="Hermes Slack Extension installer",
    no_args_is_help=True,
)


@app.callback()
def callback() -> None:
    """Hermes Slack Extension installer."""


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
