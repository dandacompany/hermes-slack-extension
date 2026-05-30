import copy

from hermes_slack_ext.core import manifest as M


def _base():
    slashes = [
        {"command": f"/cmd{i}", "description": f"c{i}", "should_escape": False,
         "url": "https://hermes-agent.local/slack/commands"}
        for i in range(50)
    ]
    slashes[5]["command"] = "/footer"
    return {
        "features": {"slash_commands": slashes},
        "settings": {"socket_mode_enabled": True, "interactivity": {"is_enabled": True}},
    }


def test_swap_preserves_count_and_settings():
    out = M.swap_slashes(_base(), drop=["footer"], add=[{"command": "/board", "description": "board"}])
    cmds = [s["command"] for s in out["features"]["slash_commands"]]
    assert len(cmds) == 50                      # 추가 1 == 제거 1
    assert "/footer" not in cmds
    assert "/board" in cmds
    assert out["settings"]["socket_mode_enabled"] is True
    assert out["settings"]["interactivity"]["is_enabled"] is True


def test_swap_added_entry_has_required_shape():
    out = M.swap_slashes(_base(), drop=["footer"], add=[{"command": "/board", "description": "board"}])
    entry = next(s for s in out["features"]["slash_commands"] if s["command"] == "/board")
    assert entry["should_escape"] is False
    assert entry["url"] == "https://hermes-agent.local/slack/commands"  # 기존 url 재사용


def test_swap_does_not_duplicate_existing():
    base = _base()
    base["features"]["slash_commands"][0]["command"] = "/board"
    out = M.swap_slashes(base, drop=["footer"], add=[{"command": "/board", "description": "x"}])
    cmds = [s["command"] for s in out["features"]["slash_commands"]]
    assert cmds.count("/board") == 1


def test_participant_manifest_has_no_slash_commands():
    pm = M.participant_manifest("Researcher")
    assert "slash_commands" not in pm["features"]
    assert pm["display_information"]["name"] == "Researcher"
    assert pm["settings"]["socket_mode_enabled"] is True


def test_fetch_full_manifest_invokes_cli(monkeypatch, tmp_path):
    calls = {}

    class FakeProc:
        stdout = '{"features": {"slash_commands": []}, "settings": {}}'

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(M.subprocess, "run", fake_run)
    out = M.fetch_full_manifest(tmp_path, "Hermes Mod", "desc")
    assert out == {"features": {"slash_commands": []}, "settings": {}}
    assert "slack" in calls["cmd"] and "manifest" in calls["cmd"]
    assert "--name" in calls["cmd"] and "Hermes Mod" in calls["cmd"]
