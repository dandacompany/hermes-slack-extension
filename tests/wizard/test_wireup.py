import json
from pathlib import Path

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.steps import wireup as W


def _profiles():
    return [
        {"profile_id": "moderator", "base_app": True, "persona_display_name": "Moderator",
         "bot_user_id": "Bmod", "env_path": ""},
        {"profile_id": "researcher", "base_app": False, "persona_display_name": "Researcher",
         "role_job": "Researcher", "personality_traits": "x", "values_and_priorities": "y",
         "speaking_style": "z", "background_context": "b", "decision_lens": "d",
         "avoided_behaviors": "a", "bot_user_id": "Bp1"},
    ]


def test_wireup_writes_allowed_users_and_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    envs = tmp_path / "envs"; envs.mkdir()
    (envs / "researcher.env").write_text("SLACK_BOT_TOKEN=x\n")
    skills_dir = tmp_path / "skills"
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({
        "features": ["meeting"], "profiles": _profiles(),
        "human_user_id": "Uhuman", "channel_id": "C1",
        "profile_env_dir": str(envs), "skills_dir": str(skills_dir),
        "staging_dir": str(tmp_path / "staging"),
    })
    # fix up researcher env_path
    ctx.data["profiles"][1]["env_path"] = str(envs / "researcher.env")
    W.WireupStep().apply(ctx)

    env = (envs / "researcher.env").read_text()
    assert "SLACK_ALLOW_BOTS=mentions" in env
    assert "Uhuman" in env and "Bmod" in env and "Bp1" in env   # all bots in allowed_users
    # moderator skill is installed
    assert (skills_dir / "hermes-meeting" / "SKILL.md").exists()
    # channel prompt staging
    assert (Path(ctx.data["staging_dir"]) / "researcher.channel-prompt.txt").exists()
    # mention-map sidecar: display name -> bot user id (for @ProfileName auto routing)
    mentions = json.loads((tmp_path / "home" / "hermes-slack-ext" / "meeting_mentions.json").read_text())
    assert mentions == {"Moderator": "Bmod", "Researcher": "Bp1"}


def test_wireup_pulls_moderator_bot_from_ctx(tmp_path, monkeypatch):
    # when the moderator profile has no bot_user_id (the real default flow),
    # ctx's moderator_bot_user_id must end up in allowed_users (C1 regression guard).
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    envs = tmp_path / "envs"; envs.mkdir()
    (envs / "researcher.env").write_text("SLACK_BOT_TOKEN=x\n")
    profs = _profiles()
    del profs[0]["bot_user_id"]  # moderator has no capture path, so it is empty
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({
        "features": ["meeting"], "profiles": profs,
        "human_user_id": "Uhuman", "moderator_bot_user_id": "Bmod2",
        "profile_env_dir": str(envs), "skills_dir": str(tmp_path / "skills"),
        "staging_dir": str(tmp_path / "staging"),
    })
    profs[1]["env_path"] = str(envs / "researcher.env")
    W.WireupStep().apply(ctx)

    env = (envs / "researcher.env").read_text()
    assert "Bmod2" in env and "Bp1" in env and "Uhuman" in env
    # also backfilled into the moderator profile
    assert profs[0]["bot_user_id"] == "Bmod2"
    # mention map uses the backfilled moderator id so @Moderator hand-off converts
    mentions = json.loads((tmp_path / "home" / "hermes-slack-ext" / "meeting_mentions.json").read_text())
    assert mentions["Moderator"] == "Bmod2" and mentions["Researcher"] == "Bp1"
