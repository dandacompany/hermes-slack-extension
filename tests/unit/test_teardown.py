import json
from pathlib import Path

from hermes_slack_ext.core import teardown as T


_PATCHED = (
    "x _board_action_locks x @self._app.command(\"/board\") x hermes_board_task_create x "
    'if name != "board" x async def send_kanban_board x '
    "_meeting_action_locks x @self._app.command(\"/meeting\") x hermes_meeting_new x "
    "async def send_meeting_room x"
)


def _install(tmp_path, *, patched=True, overlays=True):
    root = tmp_path / "h"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "gateway/platforms/slack.py").write_text(_PATCHED if patched else "clean\n")
    if overlays:
        (root / "gateway/platforms/slack_kanban_board.py").write_text("# board\n")
        (root / "gateway/platforms/slack_meeting_room.py").write_text("# meeting\n")
    bk = tmp_path / "state" / "backups" / "board"
    (bk / "gateway/platforms").mkdir(parents=True)
    (bk / "gateway/platforms/slack.py").write_text("ORIGINAL clean slack\n")
    sdir = tmp_path / "state"
    (sdir / "state.json").write_text(json.dumps({"completed": [], "data": {"install_record": {
        "features": ["board", "meeting"], "created_app_ids": ["A1"],
        "slash_dropped": ["footer", "sethome"], "backup_root": str(bk),
        "skills_dir": str(root / "skills"), "profile_env_dir": str(root / "envs")}}}))
    return root, sdir, bk


def test_diagnose_reports_patch_and_overlays(tmp_path, monkeypatch):
    # Point HERMES_HOME at a temp config so the kanban-toolset probe is hermetic
    # (never reads the developer's real ~/.hermes/config.yaml).
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("toolsets: [hermes-cli, kanban]\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))

    root, sdir, _bk = _install(tmp_path)
    d = T.diagnose(root, sdir)
    assert d["board_patched"] is True and d["meeting_patched"] is True
    assert d["kanban_toolset_enabled"] is True
    assert "gateway/platforms/slack_kanban_board.py" in d["overlays_present"]
    assert "gateway/platforms/slack_meeting_room.py" in d["overlays_present"]
    assert d["backup_present"] is True
    assert d["created_app_ids"] == ["A1"]
    assert d["has_record"] is True


def test_restore_slack_py_unpatches(tmp_path):
    root, _sdir, bk = _install(tmp_path)
    restored = T.restore_slack_py(root, bk, dry_run=False)
    assert "gateway/platforms/slack.py" in restored
    assert (root / "gateway/platforms/slack.py").read_text() == "ORIGINAL clean slack\n"


def test_restore_slack_py_dry_run_no_change(tmp_path):
    root, _sdir, bk = _install(tmp_path)
    before = (root / "gateway/platforms/slack.py").read_text()
    planned = T.restore_slack_py(root, bk, dry_run=True)
    assert "gateway/platforms/slack.py" in planned
    assert (root / "gateway/platforms/slack.py").read_text() == before


def test_remove_overlays(tmp_path):
    root, _sdir, _bk = _install(tmp_path)
    removed = T.remove_overlays(root, dry_run=False)
    assert "gateway/platforms/slack_meeting_room.py" in removed
    assert not (root / "gateway/platforms/slack_meeting_room.py").exists()
    assert not (root / "gateway/platforms/slack_kanban_board.py").exists()


def test_remove_overlays_dry_run(tmp_path):
    root, _sdir, _bk = _install(tmp_path)
    removed = T.remove_overlays(root, dry_run=True)
    assert removed
    assert (root / "gateway/platforms/slack_meeting_room.py").exists()


def test_cleanup_artifacts(tmp_path):
    home = tmp_path / "home"
    (home / "hermes-slack-ext").mkdir(parents=True)
    (home / "hermes-slack-ext/meeting_sessions.json").write_text("{}")
    (home / "hermes-slack-ext/meeting_participants.json").write_text("[]")
    # Real layout: skills_dir lives under HERMES_HOME (~/.hermes/skills).
    skills = home / "skills"; (skills / "hermes-meeting").mkdir(parents=True)
    (skills / "hermes-meeting/SKILL.md").write_text("x")
    record = {"skills_dir": str(skills)}
    removed = T.cleanup_artifacts(record, home, dry_run=False)
    assert any("meeting_sessions.json" in r for r in removed)
    assert not (home / "hermes-slack-ext/meeting_sessions.json").exists()
    assert not (skills / "hermes-meeting").exists()


def test_cleanup_artifacts_skips_out_of_bounds(tmp_path):
    # I1: even if the record points to a directory outside hermes_home, do not rmtree it (prevents data loss).
    home = tmp_path / "home"; (home / "hermes-slack-ext").mkdir(parents=True)
    outside = tmp_path / "precious"; (outside / "hermes-meeting").mkdir(parents=True)
    (outside / "hermes-meeting/keep.txt").write_text("KEEP")
    record = {"skills_dir": str(outside), "staging_dir": str(tmp_path / "precious2")}
    (tmp_path / "precious2").mkdir()
    removed = T.cleanup_artifacts(record, home, dry_run=False)
    assert (outside / "hermes-meeting").exists()       # not deleted
    assert (tmp_path / "precious2").exists()
    assert any("skipped" in r for r in removed)          # marked as skipped
