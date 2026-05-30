from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from hermes_slack_ext import __version__
from hermes_slack_ext.core.state import WizardState
from hermes_slack_ext.wizard.engine import Wizard, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts, ScriptedPrompts
from hermes_slack_ext.wizard.steps.detect import DetectStep
from hermes_slack_ext.wizard.steps.select_features import SelectFeaturesStep
from hermes_slack_ext.wizard.steps.board import BoardStep
from hermes_slack_ext.wizard.steps.slash_swap import SlashSwapStep

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


def _build_steps():
    return [DetectStep(), SelectFeaturesStep(), BoardStep(), SlashSwapStep()]


@app.command()
def install(
    hermes_root: str = typer.Option(str(Path.home() / ".hermes/hermes-agent"), "--hermes-root"),
    answers_file: Optional[str] = typer.Option(None, "--answers-file"),
    non_interactive: bool = typer.Option(False, "--non-interactive"),
    state_dir: str = typer.Option(str(Path.home() / ".hermes/hermes-slack-ext"), "--state-dir"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run the install wizard (interactive, or headless with --answers-file)."""
    root = Path(hermes_root).expanduser().resolve()
    ctx = WizardContext(hermes_root=root, non_interactive=non_interactive, dry_run=dry_run)

    if answers_file:
        answers = yaml.safe_load(Path(answers_file).read_text()) or {}
        # 비-프롬프트 값은 ctx.data로 직접 주입
        for k in ("manifest_out", "moderator_name", "backup_root"):
            if k in answers:
                ctx.data[k] = answers[k]
        # 프롬프트 키는 ScriptedPrompts로. features는 checkbox가 리스트 전체를
        # 한 번에 반환하므로 한 번의 dequeue로 전체 리스트가 나오도록 이중 래핑.
        scripted: dict = {}
        if "features" in answers:
            scripted["features"] = [answers["features"]]
        prompts: Prompts = ScriptedPrompts(scripted)
    else:
        prompts = Prompts()

    ctx.data.setdefault("backup_root", str(Path(state_dir) / "backups" / "board"))
    state = WizardState(Path(state_dir) / "state.json").load()
    Wizard(_build_steps(), prompts, state).run(ctx)
    typer.echo("설치 완료. 게이트웨이를 재시작하세요: hermes gateway restart")


if __name__ == "__main__":
    app()
