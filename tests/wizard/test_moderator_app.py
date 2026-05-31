import json
from pathlib import Path

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.steps import moderator_app as M


def test_updates_base_app_when_id_present(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.setattr(M.slack_api, "update_app",
                        lambda token, app_id, man: calls.update(app_id=app_id, man=man) or {"ok": True})
    man_path = tmp_path / "base.json"
    man_path.write_text(json.dumps({"features": {"slash_commands": []}}))
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({"features": ["meeting"], "config_token": "xoxe",
                     "base_app_id": "A_base", "base_manifest_path": str(man_path)})
    M.ModeratorAppStep().apply(ctx)
    assert calls["app_id"] == "A_base"


def test_no_base_id_is_noop_with_guidance(tmp_path, capsys):
    man_path = tmp_path / "base.json"
    man_path.write_text("{}")
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data.update({"features": ["meeting"], "base_manifest_path": str(man_path)})
    M.ModeratorAppStep().apply(ctx)  # no base_app_id -> no exception, only guidance shown
    assert "base.json" in capsys.readouterr().out
