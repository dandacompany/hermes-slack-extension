from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
import yaml

from hermes_slack_ext import __version__
from hermes_slack_ext.core import teardown, slack_api
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
from hermes_slack_ext.wizard.steps.tts import TtsStep
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
        ModeratorAppStep(), WireupStep(), TtsStep(), MeetingRuntimeStep(),
    ]


# Metadata for uninstall. Never includes secrets (tokens).
_RECORD_KEYS = (
    "features", "created_app_ids", "base_app_id", "slash_dropped",
    "backup_root", "profile_env_dir", "skills_dir", "staging_dir",
)


def _record_install(state: WizardState, ctx: WizardContext) -> None:
    record = dict(state.data.get("install_record", {}))
    for key in _RECORD_KEYS:
        val = ctx.data.get(key)
        # Merge so a resumed run's empty value can't overwrite an existing non-empty record.
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
        raise typer.BadParameter("--non-interactive must be used together with --answers-file.")

    if answers_file:
        answers = yaml.safe_load(Path(answers_file).read_text()) or {}
        # Inject non-prompt values directly into ctx.data.
        for k in ("manifest_out", "moderator_name", "backup_root", "base_app_id",
                  "channel_id", "human_user_id", "moderator_bot_user_id",
                  "profile_env_dir", "skills_dir", "staging_dir", "participant_app_ids"):
            if k in answers:
                ctx.data[k] = answers[k]
        # Prompt keys go through ScriptedPrompts. The features checkbox returns the
        # whole list at once, so double-wrap it to yield the full list in a single dequeue.
        scripted: dict = {}
        if "features" in answers:
            scripted["features"] = [answers["features"]]
        # Meeting prompt keys (scalars) — ScriptedPrompts wraps a scalar as [v], so pass them as-is.
        for k in ("profile_mode", "profile_count", "config_token", "refresh_token"):
            if k in answers:
                scripted[k] = answers[k]
        # Participant token/preset keys (<pid>_bot_token / <pid>_app_token / preset_N / <pid>_<field>).
        for k, v in answers.items():
            if k.endswith(("_bot_token", "_app_token")) or k.startswith("preset_"):
                scripted[k] = v
        # TTS step: default to text-only (skip) unless the answers file opts in;
        # pass through provider / per-profile voice / API-key answers when present.
        scripted["tts_enable"] = bool(answers.get("tts_enable", False))
        for k, v in answers.items():
            if k == "tts_provider" or k.startswith("tts_voice_") or (k.startswith("tts_") and k.endswith("_key")):
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
        typer.echo("Dry run complete — no changes were made.")
    else:
        typer.echo("Install complete. Restart the gateway: hermes gateway restart")


@app.command()
def uninstall(
    hermes_root: str = typer.Option(str(Path.home() / ".hermes/hermes-agent"), "--hermes-root"),
    state_dir: str = typer.Option(str(Path.home() / ".hermes/hermes-slack-ext"), "--state-dir"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
    delete_apps: bool = typer.Option(False, "--delete-apps",
                                     help="Delete the created participant Slack apps via apps.manifest.delete"),
    non_interactive: bool = typer.Option(False, "--non-interactive"),
) -> None:
    """Reverse the install: restore slack.py (unpatch), remove overlays, clean up meeting artifacts, and (optionally) delete created apps."""
    root = Path(hermes_root).expanduser().resolve()
    diag = teardown.diagnose(root, state_dir)
    record = teardown.load_record(state_dir)
    home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))

    typer.echo("Uninstall plan:")
    typer.echo(f"  - Restore slack.py (from backup): {'present' if diag['backup_present'] else 'missing (manual restore needed)'} @ {diag['backup_root']}")
    typer.echo(f"  - Remove overlays: {diag['overlays_present'] or 'none'}")
    if diag["created_app_ids"]:
        action = "delete" if delete_apps else "keep (use --delete-apps to delete)"
        typer.echo(f"  - Created apps: {len(diag['created_app_ids'])}: {action}")
    if dry_run:
        plan = teardown.restore_slack_py(root, diag["backup_root"], dry_run=True)
        typer.echo(f"  [dry-run] {len(plan)} file(s) to restore, "
                   f"{len(teardown.remove_overlays(root, dry_run=True))} overlay(s)")
        typer.echo("Dry run — no changes were made.")
        return

    if not yes and not non_interactive:
        typer.confirm("Proceed with the uninstall plan above?", abort=True)

    if diag["backup_present"]:
        teardown.restore_slack_py(root, diag["backup_root"])
        typer.echo("  slack.py restored.")
    else:
        typer.echo("  No backup found, so slack.py could not be restored automatically (remove the markers manually).")
    removed = teardown.remove_overlays(root)
    typer.echo(f"  {len(removed)} overlay(s) removed.")
    cleaned = teardown.cleanup_artifacts(record, home)
    typer.echo(f"  {len(cleaned)} artifact(s) cleaned up.")

    if delete_apps and diag["created_app_ids"]:
        token = os.environ.get("HSE_CONFIG_TOKEN", "")
        if not token and not non_interactive:
            token = typer.prompt("App Configuration Token (xoxe-...)", hide_input=True)
        if not token:
            typer.echo("  No config token, so skipping deletion of created apps. "
                       "app_id(s) to delete manually: " + ", ".join(diag["created_app_ids"]))
        else:
            for app_id in diag["created_app_ids"]:
                try:
                    slack_api.delete_app(token, app_id)
                    typer.echo(f"  App deleted: {app_id}")
                except slack_api.SlackAPIError as exc:
                    typer.echo(f"  App deletion failed ({app_id}): {exc.error}")

    sp = Path(state_dir) / "state.json"
    if sp.exists():
        raw = json.loads(sp.read_text(encoding="utf-8"))
        raw.setdefault("data", {})["uninstalled"] = True
        sp.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo("Uninstall complete. Restart the gateway: hermes gateway restart")


@app.command()
def doctor(
    hermes_root: str = typer.Option(str(Path.home() / ".hermes/hermes-agent"), "--hermes-root"),
    state_dir: str = typer.Option(str(Path.home() / ".hermes/hermes-slack-ext"), "--state-dir"),
) -> None:
    """Diagnose the install state (patches applied, overlays, backup, record)."""
    root = Path(hermes_root).expanduser().resolve()
    d = teardown.diagnose(root, state_dir)

    def _mark(b: bool) -> str:
        return "✓" if b else "✗"

    typer.echo(f"Hermes: {d['hermes_root']} (version: {d['version'] or 'unknown'})")
    typer.echo(f"  slack.py present : {_mark(d['slack_py_exists'])}")
    typer.echo(f"  board patched    : {_mark(d['board_patched'])}")
    typer.echo(f"  meeting patched  : {_mark(d['meeting_patched'])}")
    typer.echo(f"  kanban toolset   : {_mark(d['kanban_toolset_enabled'])}")
    typer.echo(f"  overlays         : {d['overlays_present'] or 'none'}")
    typer.echo(f"  backup available : {_mark(d['backup_present'])} @ {d['backup_root']}")
    typer.echo(f"  install record   : {_mark(d['has_record'])}"
               f" (features={d['features']}, dropped={d['slash_dropped']})")
    typer.echo(f"  created apps     : {len(d['created_app_ids'])}")
    if not d["has_record"] and (d["board_patched"] or d["meeting_patched"]):
        typer.echo("  ⚠ Patches are applied but there is no install record — "
                   "uninstall will work from the backup/markers only (created apps can't be auto-deleted).")
    if d["board_patched"] and not d["kanban_toolset_enabled"]:
        typer.echo("  ⚠ Board is patched but the `kanban` toolset is not enabled — "
                   "natural-language board management won't work (only the Add button). "
                   "Add `kanban` to config.yaml `toolsets:` and restart the gateway.")


if __name__ == "__main__":
    app()
