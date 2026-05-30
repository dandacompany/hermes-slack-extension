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
    # researcher 하나만 참가자 → 토큰 2개(bot/app)
    prompts = ScriptedPrompts({
        "researcher_bot_token": ["xoxb-r"], "researcher_app_token": ["xapp-r"],
    })
    A.SlackAppsStep().apply_with_prompts(ctx, prompts)

    assert len(created) == 1                       # moderator(base_app)는 생성 안 함
    env = Path(tmp_path / "envs" / "researcher.env").read_text()
    assert "SLACK_BOT_TOKEN=xoxb-r" in env and "SLACK_APP_TOKEN=xapp-r" in env
    # bot_user_id가 프로필에 기록됨(bot-to-bot 배선용)
    rp = next(p for p in ctx.data["profiles"] if p["profile_id"] == "researcher")
    assert rp["bot_user_id"] == "Bp1"
    assert ctx.data["created_app_ids"] == ["A_new"]
