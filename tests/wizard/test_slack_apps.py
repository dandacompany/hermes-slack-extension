import json
from pathlib import Path

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps import slack_apps as A


def _profiles():
    return [
        {"profile_id": "moderator", "base_app": True, "persona_display_name": "Moderator",
         "slack_app_display_name": "Hermes Moderator"},
        {"profile_id": "researcher", "base_app": False, "persona_display_name": "Researcher",
         "slack_app_display_name": "Hermes Researcher"},
    ]


def test_creates_apps_for_participants_only(tmp_path, monkeypatch):
    created = []
    monkeypatch.setattr(A.slack_api, "create_app",
                        lambda token, manifest: created.append(manifest) or {"app_id": "A_new"})
    monkeypatch.setattr(A.slack_api, "auth_test",
                        lambda bot: {"user_id": "Bp1", "team_id": "T"})
    monkeypatch.setattr(A.slack_api, "conversations_join", lambda bot, ch: {"ok": True})

    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({
        "features": ["meeting"], "profiles": _profiles(),
        "config_token": "xoxe-t", "channel_id": "C123",
        "profile_env_dir": str(tmp_path / "envs"),
    })
    # only researcher is a participant -> 2 tokens (bot/app)
    prompts = ScriptedPrompts({
        "researcher_bot_token": ["xoxb-r"], "researcher_app_token": ["xapp-r"],
    })
    A.SlackAppsStep().apply_with_prompts(ctx, prompts)

    assert len(created) == 1                       # moderator (base_app) is not created
    env = Path(tmp_path / "envs" / "researcher.env").read_text()
    assert "SLACK_BOT_TOKEN=xoxb-r" in env and "SLACK_APP_TOKEN=xapp-r" in env
    # bot_user_id is recorded in the profile (for bot-to-bot wiring)
    rp = next(p for p in ctx.data["profiles"] if p["profile_id"] == "researcher")
    assert rp["bot_user_id"] == "Bp1"
    assert ctx.data["created_app_ids"] == ["A_new"]


def test_dry_run_creates_no_apps_or_files(tmp_path, monkeypatch):
    # C2: --dry-run does not actually create apps or write env files.
    called = {"create": 0}
    monkeypatch.setattr(A.slack_api, "create_app",
                        lambda t, m: called.__setitem__("create", called["create"] + 1) or {"app_id": "X"})
    ctx = WizardContext(hermes_root=tmp_path, dry_run=True)
    ctx.data.update({"features": ["meeting"], "profiles": _profiles(),
                     "config_token": "xoxe-t", "profile_env_dir": str(tmp_path / "envs")})
    A.SlackAppsStep().apply_with_prompts(ctx, ScriptedPrompts({}))
    assert called["create"] == 0
    assert not (tmp_path / "envs" / "researcher.env").exists()


def test_skips_already_created_profiles(tmp_path, monkeypatch):
    # I2: profiles that already have an app_id are not re-created (idempotent re-run).
    created = []
    monkeypatch.setattr(A.slack_api, "create_app",
                        lambda t, m: created.append(m) or {"app_id": "A_new"})
    monkeypatch.setattr(A.slack_api, "auth_test", lambda b: {"user_id": "Bp1"})
    monkeypatch.setattr(A.slack_api, "conversations_join", lambda b, c: {"ok": True})
    profs = _profiles()
    profs[1]["app_id"] = "A_existing"   # researcher already created
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({"features": ["meeting"], "profiles": profs,
                     "config_token": "xoxe-t", "profile_env_dir": str(tmp_path / "envs")})
    A.SlackAppsStep().apply_with_prompts(ctx, ScriptedPrompts({}))
    assert created == []   # no new app is created


def test_rotates_config_token_when_refresh_present(tmp_path, monkeypatch):
    # I3: when a refresh token is present, rotate it and replace config_token.
    used_tokens = []
    monkeypatch.setattr(A.slack_api, "rotate_tokens",
                        lambda r: {"token": "xoxe-fresh", "refresh_token": "xoxe-r2"})
    monkeypatch.setattr(A.slack_api, "create_app",
                        lambda t, m: used_tokens.append(t) or {"app_id": "A_new"})
    monkeypatch.setattr(A.slack_api, "auth_test", lambda b: {"user_id": "Bp1"})
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({"features": ["meeting"], "profiles": _profiles(),
                     "config_token": "xoxe-old", "config_refresh_token": "xoxe-r",
                     "profile_env_dir": str(tmp_path / "envs")})
    A.SlackAppsStep().apply_with_prompts(ctx, ScriptedPrompts(
        {"researcher_bot_token": ["xoxb-r"], "researcher_app_token": ["xapp-r"]}))
    assert ctx.data["config_token"] == "xoxe-fresh"
    assert used_tokens == ["xoxe-fresh"]   # create_app uses the rotated token


def test_auth_test_failure_does_not_abort_loop(tmp_path, monkeypatch):
    # I2: when auth.test fails, bot_user_id stays empty and the exception is not propagated.
    monkeypatch.setattr(A.slack_api, "create_app", lambda t, m: {"app_id": "A_new"})

    def _boom(bot):
        raise A.slack_api.SlackAPIError("auth.test", "invalid_auth")
    monkeypatch.setattr(A.slack_api, "auth_test", _boom)
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({"features": ["meeting"], "profiles": _profiles(),
                     "config_token": "xoxe-t", "channel_id": "C1",
                     "profile_env_dir": str(tmp_path / "envs")})
    A.SlackAppsStep().apply_with_prompts(ctx, ScriptedPrompts(
        {"researcher_bot_token": ["xoxb-r"], "researcher_app_token": ["xapp-r"]}))
    rp = next(p for p in ctx.data["profiles"] if p["profile_id"] == "researcher")
    assert rp["bot_user_id"] == ""           # proceeds even on failure
    assert rp["app_id"] == "A_new"


def test_pre_created_app_ids_skip_creation(tmp_path, monkeypatch):
    # when participant_app_ids is given, create_app is not called and that app_id is reused.
    created = []
    monkeypatch.setattr(A.slack_api, "create_app",
                        lambda t, m: created.append(m) or {"app_id": "NEW"})
    monkeypatch.setattr(A.slack_api, "auth_test", lambda b: {"user_id": "Bp1"})
    monkeypatch.setattr(A.slack_api, "conversations_join", lambda b, c: {"ok": True})
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({
        "features": ["meeting"], "profiles": _profiles(),
        "config_token": "xoxe-t", "profile_env_dir": str(tmp_path / "envs"),
        "participant_app_ids": {"researcher": "A_PRE"},
    })
    prompts = ScriptedPrompts({"researcher_bot_token": ["xoxb-r"], "researcher_app_token": ["xapp-r"]})
    A.SlackAppsStep().apply_with_prompts(ctx, prompts)
    assert created == []                       # create_app not called
    rp = next(p for p in ctx.data["profiles"] if p["profile_id"] == "researcher")
    assert rp["app_id"] == "A_PRE"             # reuse the pre-created id
    assert "SLACK_BOT_TOKEN=xoxb-r" in (tmp_path / "envs" / "researcher.env").read_text()
