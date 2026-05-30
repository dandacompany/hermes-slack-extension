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
                    reason="실 Hermes 체크아웃/venv 없음")
def test_headless_meeting_setup(tmp_path, monkeypatch):
    # 클론
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "venv").symlink_to(REAL_VENV.resolve())
    shutil.copy(REAL / "gateway/platforms/slack.py", root / "gateway/platforms/slack.py")
    shutil.copy(REAL / "pyproject.toml", root / "pyproject.toml")

    # Slack API 목
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
        # 3 참가자(researcher/developer/designer) bot/app 토큰
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
    # 참가자 env 3개 생성 + allowed_users 배선(모더레이터 봇 포함)
    for pid in ("researcher", "developer", "designer"):
        env = (tmp_path / "envs" / f"{pid}.env").read_text()
        assert "SLACK_BOT_TOKEN=" in env and "SLACK_ALLOW_BOTS=mentions" in env
        assert "Bmod" in env, f"{pid}.env의 allowed_users에 모더레이터 봇 누락"
    # moderator 스킬 설치
    assert (tmp_path / "skills" / "hermes-meeting" / "SKILL.md").exists()

    # 미팅 Block Kit 런타임 패치 적용 확인
    patched = (root / "gateway/platforms/slack.py").read_text()
    assert '@self._app.command("/meeting")' in patched
    assert "hermes_meeting_new" in patched
    assert (root / "gateway/platforms/slack_meeting_room.py").exists()
    # 실 slack.py가 미팅 splice 후에도 py_compile 통과
    import subprocess as _sp
    _sp.run([str(REAL_VENV / "bin/python"), "-m", "py_compile",
             str(root / "gateway/platforms/slack.py"),
             str(root / "gateway/platforms/slack_meeting_room.py")], check=True)
    # 참가자 사이드카(HERMES_HOME 아래) — HERMES_HOME 전역 override 시 tmp/home 사용
    import json as _json
    sc = tmp_path / "home" / "hermes-slack-ext" / "meeting_participants.json"
    if sc.exists():
        assert _json.loads(sc.read_text()) == ["Researcher", "Backend", "Designer"]
