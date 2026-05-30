from __future__ import annotations

import shutil
from pathlib import Path


def backup_files(hermes_root: Path, rel_paths: list[str], backup_root: Path) -> Path:
    """Copy each existing rel_path under hermes_root into a fresh backup dir,
    preserving relative structure. Missing files are skipped. Returns the
    backup dir."""
    hermes_root = Path(hermes_root)
    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)
    for rel in rel_paths:
        src = hermes_root / rel
        if not src.exists():
            continue
        dest = backup_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return backup_root


def restore_backup(hermes_root: Path, backup_dir: Path) -> list[str]:
    """Restore every file found under backup_dir back into hermes_root.
    Returns the list of restored relative paths."""
    hermes_root = Path(hermes_root)
    backup_dir = Path(backup_dir)
    restored: list[str] = []
    for path in backup_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(backup_dir)
            dest = hermes_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            restored.append(str(rel))
    return restored
