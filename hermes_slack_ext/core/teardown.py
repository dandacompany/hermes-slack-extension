from __future__ import annotations

import json
import shutil
from pathlib import Path

from hermes_slack_ext.core import backups, hermes, patcher

# install이 추가하는 오버레이 파일(원복 시 삭제 — 백업에 없으므로 별도 제거).
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
        "overlays_present": [m for m in OVERLAY_MODULES if (root / m).exists()],
        "backup_root": str(backup_root),
        "backup_present": (backup_root / "gateway/platforms/slack.py").exists(),
        "features": record.get("features", []),
        "created_app_ids": record.get("created_app_ids", []),
        "slash_dropped": record.get("slash_dropped", []),
        "has_record": bool(record),
    }


def restore_slack_py(hermes_root, backup_root, dry_run: bool = False) -> list:
    """백업(패치 전 원본)을 복원해 slack.py를 언패치한다. 복원/예정 rel 목록 반환."""
    backup_root = Path(backup_root)
    if not (backup_root / "gateway/platforms/slack.py").exists():
        return []
    if dry_run:
        return [str(p.relative_to(backup_root))
                for p in backup_root.rglob("*") if p.is_file()]
    return backups.restore_backup(hermes_root, backup_root)


def remove_overlays(hermes_root, dry_run: bool = False) -> list:
    """install이 복사한 오버레이 모듈/테스트 삭제. 제거/예정 rel 목록 반환."""
    root = Path(hermes_root)
    removed = []
    for rel in OVERLAY_MODULES:
        f = root / rel
        if f.exists():
            removed.append(rel)
            if not dry_run:
                f.unlink()
    return removed


def cleanup_artifacts(record: dict, hermes_home, dry_run: bool = False) -> list:
    """미팅 사이드카·세션스토어·베이스 매니페스트·모더레이터 스킬·스테이징 정리.
    프로필 .env(토큰 보관)는 건드리지 않는다 — 호출부가 별도 확인 후 처리."""
    home = Path(hermes_home)
    targets = [
        home / "hermes-slack-ext" / "meeting_participants.json",
        home / "hermes-slack-ext" / "meeting_sessions.json",
        home / "hermes-slack-ext" / "base-manifest.json",
    ]
    if record.get("skills_dir"):
        targets.append(Path(record["skills_dir"]) / "hermes-meeting")
    if record.get("staging_dir"):
        targets.append(Path(record["staging_dir"]))
    removed = []
    for t in targets:
        if t.exists():
            removed.append(str(t))
            if not dry_run:
                if t.is_dir():
                    shutil.rmtree(t)
                else:
                    t.unlink()
    return removed
