from pathlib import Path

from hermes_slack_ext.core.backups import backup_files, restore_backup


def test_backup_and_restore(tmp_path):
    root = tmp_path / "hermes"
    (root / "gateway/platforms").mkdir(parents=True)
    target = root / "gateway/platforms/slack.py"
    target.write_text("original\n")

    backup_dir = backup_files(root, ["gateway/platforms/slack.py"], tmp_path / "backups")
    assert (backup_dir / "gateway/platforms/slack.py").read_text() == "original\n"

    target.write_text("patched\n")
    restore_backup(root, backup_dir)
    assert target.read_text() == "original\n"


def test_backup_skips_missing_files(tmp_path):
    root = tmp_path / "hermes"
    root.mkdir()
    backup_dir = backup_files(root, ["does/not/exist.py"], tmp_path / "backups")
    assert backup_dir.exists()
    assert not (backup_dir / "does/not/exist.py").exists()
