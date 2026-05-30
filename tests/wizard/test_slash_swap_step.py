import json
from pathlib import Path

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.steps import slash_swap as S


def test_slash_swap_writes_swapped_manifest(tmp_path, monkeypatch):
    fake = {
        "features": {"slash_commands": [
            {"command": "/footer", "description": "f", "should_escape": False,
             "url": "https://hermes-agent.local/slack/commands"},
        ]},
        "settings": {"socket_mode_enabled": True, "interactivity": {"is_enabled": True}},
    }
    monkeypatch.setattr(S.manifest, "fetch_full_manifest", lambda *a, **k: fake)

    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data["features"] = ["board"]
    ctx.data["manifest_out"] = str(tmp_path / "base-manifest.json")
    ctx.data["moderator_name"] = "Hermes Moderator"
    S.SlashSwapStep().apply(ctx)

    written = json.loads(Path(ctx.data["manifest_out"]).read_text())
    cmds = [s["command"] for s in written["features"]["slash_commands"]]
    assert "/board" in cmds and "/footer" not in cmds
