"""Block Kit /meeting 회의룸 런타임 (Hermes 게이트웨이 오버레이).

순수 함수 모음 — slack.py에 splice되는 slack_meeting_methods.pyfrag가 호출한다.
세션 메타는 일반 Slack 메시지 세션과 분리해 JSON 파일에 영속한다.
UI/액션 명세: hermes-slack-meeting-room references/block-kit-meeting-ui.md.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

ACTION_PREFIX = "hermes_meeting_"

MODE_OPTIONS = ["mixed", "sequential", "parallel", "directed"]
ROUTING_OPTIONS = ["auto", "manual"]
VOICE_OPTIONS = ["voice-summary", "text-only", "voice-full", "hybrid"]
STATUS_LABELS = {"setup": "준비", "active": "진행 중", "ended": "종료"}

_MAX_BLOCKS = 49


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def store_path() -> Path:
    return _hermes_home() / "hermes-slack-ext" / "meeting_sessions.json"


def load_store() -> dict:
    p = store_path()
    if not p.exists():
        return {"version": 1, "meetings": {}, "current": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"version": 1, "meetings": {}, "current": {}}
    data.setdefault("version", 1)
    data.setdefault("meetings", {})
    data.setdefault("current", {})
    return data


def save_store(store: dict) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".meeting.", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def gen_meeting_id(now: float) -> str:
    return "mtg-" + time.strftime("%m%d-%H%M%S", time.localtime(now))


def create_meeting(store: dict, *, channel_id: str, user_id: str, title: str,
                   participants: list, turns: str, mode: str, routing_mode: str,
                   voice_mode: str, meeting_id: str) -> tuple:
    meeting = {
        "id": meeting_id,
        "channel_id": channel_id,
        "user_id": user_id,
        "title": title,
        "participants": list(participants),
        "turns": str(turns),
        "mode": mode,
        "routing_mode": routing_mode,
        "voice_mode": voice_mode,
        "status": "setup",
        "session_thread_id": f"meeting:{channel_id}:{meeting_id}",
    }
    store["meetings"][meeting_id] = meeting
    store["current"][f"{channel_id}:{user_id}"] = meeting_id
    return meeting_id, store


def get_meeting(store: dict, meeting_id: str) -> dict | None:
    return store.get("meetings", {}).get(meeting_id)


def list_meetings(store: dict, channel_id: str) -> list:
    rows = [m for m in store.get("meetings", {}).values()
            if m.get("channel_id") == channel_id]
    rows.sort(key=lambda m: m.get("id", ""), reverse=True)
    return rows


def set_status(store: dict, meeting_id: str, status: str) -> dict:
    m = get_meeting(store, meeting_id)
    if m is not None:
        m["status"] = status
    return store
