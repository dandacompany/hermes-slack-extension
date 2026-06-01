from __future__ import annotations

import json
import shutil
from pathlib import Path

from hermes_slack_ext.core import hermes, patcher

# Overlay files added by install (removed on uninstall — they are not in the backup, so they must be deleted separately).
OVERLAY_MODULES = [
    "gateway/platforms/slack_kanban_board.py",
    "gateway/platforms/slack_meeting_room.py",
    "tests/test_slack_kanban_board.py",
    "tests/test_slack_meeting_room.py",
]


def load_record(state_dir) -> dict:
    p = Path(state_dir) / "state.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return raw.get("data", {}).get("install_record", {})


def _default_backup_root(state_dir) -> Path:
    return Path(state_dir) / "backups" / "board"


def diagnose(hermes_root, state_dir) -> dict:
    root = Path(hermes_root)
    slack_py = root / "gateway/platforms/slack.py"
    text = slack_py.read_text(encoding="utf-8") if slack_py.exists() else ""
    record = load_record(state_dir)
    backup_root = Path(record.get("backup_root") or _default_backup_root(state_dir))
    return {
        "hermes_root": str(root),
        "version": hermes.detect_version(root),
        "slack_py_exists": slack_py.exists(),
        "board_patched": patcher.board_markers_present(text) if text else False,
        "meeting_patched": patcher.meeting_markers_present(text) if text else False,
        "kanban_toolset_enabled": hermes.kanban_toolset_enabled(),
        "overlays_present": [m for m in OVERLAY_MODULES if (root / m).exists()],
        "backup_root": str(backup_root),
        "backup_present": (backup_root / "gateway/platforms/slack.py").exists(),
        "features": record.get("features", []),
        "created_app_ids": record.get("created_app_ids", []),
        "slash_dropped": record.get("slash_dropped", []),
        "has_record": bool(record),
    }


_SLACK_REL = "gateway/platforms/slack.py"


def restore_slack_py(hermes_root, backup_root, dry_run: bool = False) -> list:
    """Unpatch by restoring *only the pre-patch original slack.py* from the backup.

    Overlays are not restored from the backup (remove_overlays deletes them
    separately, which avoids a recreate-then-delete cycle). Returns the list of
    restored/planned relative paths."""
    src = Path(backup_root) / _SLACK_REL
    if not src.exists():
        return []
    if dry_run:
        return [_SLACK_REL]
    dest = Path(hermes_root) / _SLACK_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return [_SLACK_REL]


def remove_overlays(hermes_root, dry_run: bool = False) -> list:
    """Delete the overlay modules/tests that install copied in. Returns the list of removed/planned relative paths."""
    root = Path(hermes_root)
    removed = []
    for rel in OVERLAY_MODULES:
        f = root / rel
        if f.exists():
            removed.append(rel)
            if not dry_run:
                f.unlink()
    return removed


def _within(child: Path, root: Path) -> bool:
    """Whether child is under root (or root itself). Resolve before comparing to defeat symlinks/`..`."""
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def cleanup_artifacts(record: dict, hermes_home, dry_run: bool = False) -> list:
    """Clean up the meeting sidecar, session store, base manifest, moderator skill, and staging dir.
    The profile .env (which holds tokens) is left untouched — the caller handles it after a separate confirmation.

    Because this is destructive, directories that come from the record
    (skills_dir/staging_dir) are deleted only when they resolve to a path under
    hermes_home. If a corrupted/tampered state points at an arbitrary path
    outside hermes_home, it is skipped and marked 'skipped:' (to prevent an
    rmtree of an arbitrary path)."""
    home = Path(hermes_home)
    targets = [
        home / "hermes-slack-ext" / "meeting_participants.json",
        home / "hermes-slack-ext" / "meeting_mentions.json",
        home / "hermes-slack-ext" / "meeting_sessions.json",
        home / "hermes-slack-ext" / "base-manifest.json",
    ]
    if record.get("skills_dir"):
        targets.append(Path(record["skills_dir"]) / "hermes-meeting")
    if record.get("staging_dir"):
        targets.append(Path(record["staging_dir"]))
    removed = []
    for t in targets:
        if not t.exists():
            continue
        if not _within(t, home):
            removed.append(f"skipped(outside): {t}")  # outside hermes_home — not deleted, for safety
            continue
        removed.append(str(t))
        if not dry_run:
            if t.is_dir():
                shutil.rmtree(t)
            else:
                t.unlink()
    return removed
