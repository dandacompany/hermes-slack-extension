import json
from pathlib import Path

from typer.testing import CliRunner

import hermes_slack_ext.core.slack_api as slack_api
from hermes_slack_ext import cli


def _installed(tmp_path):
    root = tmp_path / "h"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "gateway/platforms/slack.py").write_text(
        '_board_action_locks @self._app.command("/board") hermes_board_task_create '
        'if name != "board" async def send_kanban_board PATCHED\n')
    (root / "gateway/platforms/slack_kanban_board.py").write_text("# board\n")
    (root / "gateway/platforms/slack_meeting_room.py").write_text("# meeting\n")
    sdir = tmp_path / "state"
    bk = sdir / "backups" / "board"
    (bk / "gateway/platforms").mkdir(parents=True)
    (bk / "gateway/platforms/slack.py").write_text("ORIGINAL\n")
    (sdir / "state.json").write_text(json.dumps({"completed": [], "data": {"install_record": {
        "features": ["board", "meeting"], "created_app_ids": ["A1", "A2"],
        "backup_root": str(bk), "skills_dir": str(root / "skills")}}}))
    return root, sdir


def test_uninstall_dry_run_changes_nothing(tmp_path, monkeypatch):
    root, sdir = _installed(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    res = CliRunner().invoke(cli.app, [
        "uninstall", "--hermes-root", str(root), "--state-dir", str(sdir),
        "--dry-run", "--yes"])
    assert res.exit_code == 0, res.stdout
    assert (root / "gateway/platforms/slack_kanban_board.py").exists()
    assert "PATCHED" in (root / "gateway/platforms/slack.py").read_text()


def test_uninstall_restores_and_removes(tmp_path, monkeypatch):
    root, sdir = _installed(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    res = CliRunner().invoke(cli.app, [
        "uninstall", "--hermes-root", str(root), "--state-dir", str(sdir), "--yes"])
    assert res.exit_code == 0, res.stdout
    assert (root / "gateway/platforms/slack.py").read_text() == "ORIGINAL\n"
    assert not (root / "gateway/platforms/slack_kanban_board.py").exists()
    assert not (root / "gateway/platforms/slack_meeting_room.py").exists()


def test_uninstall_deletes_apps_with_token(tmp_path, monkeypatch):
    root, sdir = _installed(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HSE_CONFIG_TOKEN", "xoxe-tok")
    deleted = []
    monkeypatch.setattr(slack_api, "delete_app",
                        lambda token, app_id: deleted.append((token, app_id)) or {"ok": True})
    res = CliRunner().invoke(cli.app, [
        "uninstall", "--hermes-root", str(root), "--state-dir", str(sdir),
        "--yes", "--delete-apps"])
    assert res.exit_code == 0, res.stdout
    assert [a for _t, a in deleted] == ["A1", "A2"]
    assert "xoxe-tok" not in res.stdout


def test_uninstall_delete_apps_without_token_skips(tmp_path, monkeypatch):
    root, sdir = _installed(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("HSE_CONFIG_TOKEN", raising=False)
    called = []
    monkeypatch.setattr(slack_api, "delete_app", lambda t, a: called.append(a))
    res = CliRunner().invoke(cli.app, [
        "uninstall", "--hermes-root", str(root), "--state-dir", str(sdir),
        "--yes", "--delete-apps", "--non-interactive"])
    assert res.exit_code == 0, res.stdout
    assert called == []
