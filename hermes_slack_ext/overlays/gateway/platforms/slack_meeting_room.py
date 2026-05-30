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


# ----- 액션 값 코덱 (버튼 value JSON; meeting_id를 자족적으로 운반) -----

def action_value(meeting_id: str, action: str, *, profile: str | None = None) -> str:
    payload = {"meeting_id": meeting_id, "action": action}
    if profile is not None:
        payload["profile"] = profile
    return json.dumps(payload, ensure_ascii=False)


def parse_action_value(value: str) -> dict:
    try:
        data = json.loads(value or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


# ----- Prompt Contract 빌더 (block-kit-meeting-ui.md) -----

_SESSION_NOTE = (
    "세션: 이 회의는 Slack Block Kit `/meeting` UI에서 생성된 전용 meeting 세션입니다. "
    "일반 @멘션 대화와 분리해서 진행하고, 시작/이어쓰기/종료/다음 발언자 선택은 "
    "`/meeting` UI 액션으로만 받습니다. 먼저 setup 초안을 보여주고 참가자를 멘션하지 마세요."
)


def build_start_prompt(meeting: dict) -> str:
    parts = ", ".join(meeting.get("participants", []))
    return (
        f"/meeting {meeting.get('title', '')}\n\n"
        f"참석자: {parts}\n"
        f"턴수: {meeting.get('turns', '')}턴\n"
        f"진행: {meeting.get('mode', '')}\n"
        f"진행 제어: {meeting.get('routing_mode', '')}\n"
        f"음성: {meeting.get('voice_mode', '')}\n"
        f"{_SESSION_NOTE}"
    )


def build_continue_prompt(meeting: dict, text: str) -> str:
    return text.strip()


def build_next_prompt(meeting: dict, profile: str) -> str:
    return (
        f"{profile} 1턴입니다. "
        f"manual 라우팅: 이번 턴은 {profile}에게만 발언을 요청하고, "
        f"다른 참가자는 호출하지 마세요."
    )


def build_end_prompt(meeting: dict) -> str:
    return (
        "회의를 종료합니다. 지금까지 논의를 결정/액션아이템 중심으로 요약하고, "
        "남은 미해결 항목을 정리해 마무리(finalize)하세요. 추가 참가자 호출은 하지 마세요."
    )
