import json
from pathlib import Path

from typer.testing import CliRunner

from hermes_slack_ext import cli


def test_doctor_reports_state(tmp_path):
    root = tmp_path / "h"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "gateway/platforms/slack.py").write_text(
        '_board_action_locks @self._app.command("/board") hermes_board_task_create '
        'if name != "board" async def send_kanban_board\n')
    (root / "gateway/platforms/slack_kanban_board.py").write_text("# board\n")
    sdir = tmp_path / "state"; sdir.mkdir()
    (sdir / "state.json").write_text(json.dumps({"completed": [], "data": {"install_record": {
        "features": ["board"], "created_app_ids": []}}}))
    res = CliRunner().invoke(cli.app, ["doctor", "--hermes-root", str(root), "--state-dir", str(sdir)])
    assert res.exit_code == 0, res.stdout
    assert "board" in res.stdout
    assert "patched" in res.stdout.lower() or "패치" in res.stdout


def test_doctor_on_clean_checkout(tmp_path):
    root = tmp_path / "h"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "gateway/platforms/slack.py").write_text("clean, no markers\n")
    sdir = tmp_path / "state"; sdir.mkdir()
    res = CliRunner().invoke(cli.app, ["doctor", "--hermes-root", str(root), "--state-dir", str(sdir)])
    assert res.exit_code == 0, res.stdout
    assert res.stdout.strip()
