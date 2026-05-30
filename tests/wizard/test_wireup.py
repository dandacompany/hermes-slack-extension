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


def test_wireup_writes_allowed_users_and_skill(tmp_path):
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
    # researcher env_path 보정
    ctx.data["profiles"][1]["env_path"] = str(envs / "researcher.env")
    W.WireupStep().apply(ctx)

    env = (envs / "researcher.env").read_text()
    assert "SLACK_ALLOW_BOTS=mentions" in env
    assert "Uhuman" in env and "Bmod" in env and "Bp1" in env   # allowed_users에 모든 봇
    # moderator 스킬 설치됨
    assert (skills_dir / "hermes-meeting" / "SKILL.md").exists()
    # 채널 프롬프트 스테이징
    assert (Path(ctx.data["staging_dir"]) / "researcher.channel-prompt.txt").exists()
