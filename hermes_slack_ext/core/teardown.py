from __future__ import annotations

import json
import shutil
from pathlib import Path

from hermes_slack_ext.core import hermes, patcher

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


_SLACK_REL = "gateway/platforms/slack.py"


def restore_slack_py(hermes_root, backup_root, dry_run: bool = False) -> list:
    """백업의 *패치 전 원본 slack.py만* 복원해 언패치한다(오버레이는 remove_overlays가
    별도 삭제하므로 백업에서 되살리지 않는다 — 재생성→재삭제 방지). 복원/예정 rel 반환."""
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


def _within(child: Path, root: Path) -> bool:
    """child가 root 하위(또는 root 자신)인지. 심볼릭/`..` 회피 위해 resolve 후 비교."""
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def cleanup_artifacts(record: dict, hermes_home, dry_run: bool = False) -> list:
    """미팅 사이드카·세션스토어·베이스 매니페스트·모더레이터 스킬·스테이징 정리.
    프로필 .env(토큰 보관)는 건드리지 않는다 — 호출부가 별도 확인 후 처리.

    파괴적 명령이므로, record에서 온 디렉터리(skills_dir·staging_dir)는 hermes_home
    하위로 resolve되는 경우에만 삭제한다. 손상/변조된 state가 임의 경로를 지목해도
    hermes_home 밖이면 건너뛰고 'skipped:' 로 표시한다(임의 경로 rmtree 방지)."""
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
        if not t.exists():
            continue
        if not _within(t, home):
            removed.append(f"skipped(밖): {t}")  # hermes_home 밖 — 안전상 삭제 안 함
            continue
        removed.append(str(t))
        if not dry_run:
            if t.is_dir():
                shutil.rmtree(t)
            else:
                t.unlink()
    return removed
