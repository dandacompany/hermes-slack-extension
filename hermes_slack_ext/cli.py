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
from hermes_slack_ext.wizard.steps.meeting_profiles import MeetingProfilesStep
from hermes_slack_ext.wizard.steps.slack_config_token import SlackConfigTokenStep
from hermes_slack_ext.wizard.steps.slack_apps import SlackAppsStep
from hermes_slack_ext.wizard.steps.moderator_app import ModeratorAppStep
from hermes_slack_ext.wizard.steps.wireup import WireupStep
from hermes_slack_ext.wizard.steps.meeting_runtime import MeetingRuntimeStep

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
    return [
        DetectStep(), SelectFeaturesStep(), BoardStep(), SlashSwapStep(),
        MeetingProfilesStep(), SlackConfigTokenStep(), SlackAppsStep(),
        ModeratorAppStep(), WireupStep(), MeetingRuntimeStep(),
    ]


# 원복(uninstall)용 메타. 시크릿(토큰) 절대 미포함.
_RECORD_KEYS = (
    "features", "created_app_ids", "base_app_id", "slash_dropped",
    "backup_root", "profile_env_dir", "skills_dir", "staging_dir",
)


def _record_install(state: WizardState, ctx: WizardContext) -> None:
    record = dict(state.data.get("install_record", {}))
    for key in _RECORD_KEYS:
        val = ctx.data.get(key)
        # 재개 실행에서 빈 값이 기존 비어있지 않은 기록을 덮어쓰지 않도록 merge.
        if val in (None, [], "", {}) and record.get(key) not in (None, [], "", {}):
            continue
        if val is not None:
            record[key] = val
    state.data["install_record"] = record
    state.save()


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

    if non_interactive and not answers_file:
        raise typer.BadParameter("--non-interactive 는 --answers-file 과 함께 사용하세요.")

    if answers_file:
        answers = yaml.safe_load(Path(answers_file).read_text()) or {}
        # 비-프롬프트 값은 ctx.data로 직접 주입
        for k in ("manifest_out", "moderator_name", "backup_root", "base_app_id",
                  "channel_id", "human_user_id", "moderator_bot_user_id",
                  "profile_env_dir", "skills_dir", "staging_dir"):
            if k in answers:
                ctx.data[k] = answers[k]
        # 프롬프트 키는 ScriptedPrompts로. features는 checkbox가 리스트 전체를
        # 한 번에 반환하므로 한 번의 dequeue로 전체 리스트가 나오도록 이중 래핑.
        scripted: dict = {}
        if "features" in answers:
            scripted["features"] = [answers["features"]]
        # 미팅 프롬프트 키(스칼라) — ScriptedPrompts가 스칼라를 [v]로 감싸므로 그대로 전달
        for k in ("profile_mode", "profile_count", "config_token", "refresh_token"):
            if k in answers:
                scripted[k] = answers[k]
        # 참가자 토큰/프리셋 키(<pid>_bot_token / <pid>_app_token / preset_N / <pid>_<field>)
        for k, v in answers.items():
            if k.endswith(("_bot_token", "_app_token")) or k.startswith("preset_"):
                scripted[k] = v
        prompts: Prompts = ScriptedPrompts(scripted)
    else:
        prompts = Prompts()

    ctx.data.setdefault("backup_root", str(Path(state_dir) / "backups" / "board"))
    state = WizardState(Path(state_dir) / "state.json").load()
    Wizard(_build_steps(), prompts, state).run(ctx)
    if not dry_run:
        _record_install(state, ctx)
    if dry_run:
        typer.echo("드라이런 완료 — 실제 변경 없음.")
    else:
        typer.echo("설치 완료. 게이트웨이를 재시작하세요: hermes gateway restart")


if __name__ == "__main__":
    app()
