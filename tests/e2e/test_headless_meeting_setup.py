import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import hermes_slack_ext.core.slack_api as slack_api
from hermes_slack_ext import cli

REAL = Path(os.environ.get("HERMES_ROOT", str(Path.home() / ".hermes/hermes-agent")))
REAL_VENV = REAL / "venv"


@pytest.mark.skipif(not (REAL / "gateway/platforms/slack.py").exists() or not REAL_VENV.exists(),
                    reason="no real Hermes checkout/venv")
def test_headless_meeting_setup(tmp_path, monkeypatch):
    # clone
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "venv").symlink_to(REAL_VENV.resolve())
    shutil.copy(REAL / "gateway/platforms/slack.py", root / "gateway/platforms/slack.py")
    shutil.copy(REAL / "pyproject.toml", root / "pyproject.toml")

    # Slack API mocks
    monkeypatch.setattr(slack_api, "rotate_tokens", lambda r: {"token": "xoxe-fresh", "refresh_token": "xoxe-r2"})
    monkeypatch.setattr(slack_api, "create_app", lambda t, m: {"app_id": "A_p"})
    monkeypatch.setattr(slack_api, "update_app", lambda t, a, m: {"ok": True})
    monkeypatch.setattr(slack_api, "auth_test", lambda b: {"user_id": "Bx", "team_id": "T"})
    monkeypatch.setattr(slack_api, "conversations_join", lambda b, c: {"ok": True})

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)

    answers = {
        "features": ["meeting"],
        "manifest_out": str(tmp_path / "base.json"),
        "profile_mode": "default",
        "config_token": "xoxe-t", "refresh_token": "xoxe-r",
        "channel_id": "C1", "human_user_id": "Uhuman",
        "moderator_bot_user_id": "Bmod",
        "profile_env_dir": str(tmp_path / "envs"),
        "skills_dir": str(tmp_path / "skills"),
        "staging_dir": str(tmp_path / "staging"),
        # bot/app tokens for 3 participants (researcher/developer/designer)
        "researcher_bot_token": "xoxb-r", "researcher_app_token": "xapp-r",
        "developer_bot_token": "xoxb-d", "developer_app_token": "xapp-d",
        "designer_bot_token": "xoxb-g", "designer_app_token": "xapp-g",
    }
    import yaml
    af = tmp_path / "answers.yaml"
    af.write_text(yaml.safe_dump(answers))

    result = CliRunner().invoke(cli.app, [
        "install", "--hermes-root", str(root), "--answers-file", str(af),
        "--non-interactive", "--state-dir", str(tmp_path / "state"),
    ])
    assert result.exit_code == 0, result.stdout
    # 3 participant env files created + allowed_users wiring (including the moderator bot)
    for pid in ("researcher", "developer", "designer"):
        env = (tmp_path / "envs" / f"{pid}.env").read_text()
        assert "SLACK_BOT_TOKEN=" in env and "SLACK_ALLOW_BOTS=mentions" in env
        assert "Bmod" in env, f"moderator bot missing from allowed_users in {pid}.env"
    # moderator skill installed
    assert (tmp_path / "skills" / "hermes-meeting" / "SKILL.md").exists()

    # verify the meeting Block Kit runtime patch is applied
    patched = (root / "gateway/platforms/slack.py").read_text()
    assert '@self._app.command("/meeting")' in patched
    assert "hermes_meeting_new" in patched
    assert (root / "gateway/platforms/slack_meeting_room.py").exists()
    # the real slack.py still passes py_compile after the meeting splice
    import subprocess as _sp
    _sp.run([str(REAL_VENV / "bin/python"), "-m", "py_compile",
             str(root / "gateway/platforms/slack.py"),
             str(root / "gateway/platforms/slack_meeting_room.py")], check=True)
    # participant sidecar (under HERMES_HOME) -- uses tmp/home when HERMES_HOME is globally overridden
    import json as _json
    sc = tmp_path / "home" / "hermes-slack-ext" / "meeting_participants.json"
    if sc.exists():
        assert _json.loads(sc.read_text()) == ["Researcher", "Backend", "Designer"]
