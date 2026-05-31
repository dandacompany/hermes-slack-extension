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
        # 실제 Slack 스레드 ts로 런타임에 설정한다(회의 루트 메시지 게시 후). 합성 문자열을
        # thread_id로 쓰면 Slack 답글 게시가 invalid_thread_ts로 실패하므로 빈 값으로 둔다.
        "session_thread_id": "",
    }
    store["meetings"][meeting_id] = meeting
    store["current"][f"{channel_id}:{user_id}"] = meeting_id
    return meeting_id, store


def set_session_thread(store: dict, meeting_id: str, thread_ts: str) -> dict:
    """회의의 전용 세션 스레드를 실제 Slack 메시지 ts로 고정한다. 이 ts가 (a)Slack 답글
    스레드, (b)에이전트 세션 키 분리에 동시에 쓰인다(일반 @멘션 세션과 분리)."""
    m = get_meeting(store, meeting_id)
    if m is not None:
        m["session_thread_id"] = thread_ts
    return store


def build_room_anchor_text(meeting: dict) -> str:
    """회의 루트(앵커) 메시지 — 채널에 게시하고 그 ts를 전용 세션 스레드로 사용한다."""
    parts = ", ".join(meeting.get("participants", [])) or "—"
    return (f":clipboard: *회의 룸 — {meeting.get('title', '(제목 없음)')}*\n"
            f"참석자: {parts}\n_이 스레드에서 회의가 진행됩니다._")


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
    # 헤더가 "/"로 시작하면 게이트웨이가 슬래시 명령으로 재파싱하므로(message_type과
    # 무관) 선행 슬래시 없이 회의 setup 신호를 전달한다.
    return (
        f"회의 setup 시작 — 주제: {meeting.get('title', '')}\n\n"
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


# ----- Block Kit 렌더러 -----

def _btn(text: str, action_id: str, value: str, *, style: str | None = None) -> dict:
    el = {"type": "button", "text": {"type": "plain_text", "text": text}, "action_id": action_id}
    if value:
        el["value"] = value
    if style:
        el["style"] = style
    return el


def _meeting_row_blocks(meeting: dict) -> list:
    mid = meeting["id"]
    status = STATUS_LABELS.get(meeting.get("status", ""), meeting.get("status", ""))
    parts = ", ".join(meeting.get("participants", [])) or "—"
    section = {
        "type": "section",
        "block_id": f"meeting-{mid}",
        "text": {"type": "mrkdwn",
                 "text": f"*{meeting.get('title', '(제목 없음)')}*  ·  _{status}_\n참석자: {parts}"},
    }
    base = [
        _btn("시작", f"{ACTION_PREFIX}start", action_value(mid, "start"), style="primary"),
        _btn("이어쓰기", f"{ACTION_PREFIX}continue_open", action_value(mid, "continue")),
        _btn("종료", f"{ACTION_PREFIX}end", action_value(mid, "end"), style="danger"),
    ]
    blocks = [section, {"type": "actions", "block_id": f"meeting-act-{mid}", "elements": base}]
    # manual 라우팅: 모든 참가자에 next 버튼(별도 actions 블록 — Slack은 블록당 25개 허용).
    if meeting.get("routing_mode") == "manual":
        next_btns = [
            _btn(f"다음: {p}", f"{ACTION_PREFIX}next", action_value(mid, "next", profile=p))
            for p in meeting.get("participants", [])[:24]
        ]
        if next_btns:
            blocks.append({"type": "actions", "block_id": f"meeting-next-{mid}", "elements": next_btns})
    return blocks


def build_meeting_room_blocks(store: dict, channel_id: str) -> tuple:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Hermes Meeting Room"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": "회의 세션은 이 UI로만 제어되며 일반 @멘션 대화와 분리됩니다."}]},
        {"type": "actions", "elements": [
            _btn("새 회의 시작", f"{ACTION_PREFIX}new_open", "", style="primary"),
            _btn("새로고침", f"{ACTION_PREFIX}refresh", ""),
        ]},
        {"type": "divider"},
    ]
    rows = list_meetings(store, channel_id)
    if not rows:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": "_아직 회의가 없습니다. `새 회의 시작`을 누르세요._"}]})
    for m in rows:
        row = _meeting_row_blocks(m)
        if len(blocks) + len(row) > _MAX_BLOCKS:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": "_표시 한도를 초과한 회의는 생략됨._"}]})
            break
        blocks.extend(row)
    return "Hermes Meeting Room", blocks


def _option(value: str) -> dict:
    return {"text": {"type": "plain_text", "text": value}, "value": value}


def _select_input(block_id: str, label: str, options: list, initial: str) -> dict:
    return {
        "type": "input", "block_id": block_id, "label": {"type": "plain_text", "text": label},
        "element": {"type": "static_select", "action_id": "v",
                    "options": [_option(o) for o in options],
                    "initial_option": _option(initial)},
    }


def new_meeting_modal_view(channel_id: str, user_id: str, participant_names: list) -> dict:
    if participant_names:
        participants_element = {
            "type": "multi_static_select", "action_id": "v",
            "options": [_option(p) for p in participant_names],
            "initial_options": [_option(p) for p in participant_names],
        }
    else:
        participants_element = {"type": "plain_text_input", "action_id": "v",
                                "placeholder": {"type": "plain_text", "text": "쉼표로 구분"}}
    return {
        "type": "modal", "callback_id": f"{ACTION_PREFIX}new",
        "private_metadata": json.dumps({"channel_id": channel_id, "user_id": user_id}),
        "title": {"type": "plain_text", "text": "새 회의"},
        "submit": {"type": "plain_text", "text": "생성"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {"type": "input", "block_id": "topic", "label": {"type": "plain_text", "text": "주제·목표"},
             "element": {"type": "plain_text_input", "action_id": "v"}},
            {"type": "input", "block_id": "participants",
             "label": {"type": "plain_text", "text": "참석자"}, "element": participants_element},
            {"type": "input", "block_id": "turns", "label": {"type": "plain_text", "text": "턴수"},
             "element": {"type": "plain_text_input", "action_id": "v", "initial_value": "4"}},
            _select_input("mode", "진행 모드", MODE_OPTIONS, "mixed"),
            _select_input("routing", "진행 제어", ROUTING_OPTIONS, "auto"),
            _select_input("voice", "음성 모드", VOICE_OPTIONS, "voice-summary"),
        ],
    }


def continue_modal_view(meeting_id: str) -> dict:
    return {
        "type": "modal", "callback_id": f"{ACTION_PREFIX}continue", "private_metadata": meeting_id,
        "title": {"type": "plain_text", "text": "이어쓰기"},
        "submit": {"type": "plain_text", "text": "전송"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [{"type": "input", "block_id": "msg",
                    "label": {"type": "plain_text", "text": "메시지"},
                    "element": {"type": "plain_text_input", "action_id": "v", "multiline": True}}],
    }


def parse_new_meeting_submission(values: dict) -> dict:
    def _v(block_id):
        return values.get(block_id, {}).get("v", {})

    parts_el = _v("participants")
    if parts_el.get("type") == "multi_static_select":
        participants = [o["value"] for o in parts_el.get("selected_options", [])]
    else:
        raw = parts_el.get("value", "") or ""
        participants = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
    return {
        "title": _v("topic").get("value", "").strip(),
        "participants": participants,
        "turns": _v("turns").get("value", "4").strip() or "4",
        "mode": (_v("mode").get("selected_option") or {}).get("value", "mixed"),
        "routing_mode": (_v("routing").get("selected_option") or {}).get("value", "auto"),
        "voice_mode": (_v("voice").get("selected_option") or {}).get("value", "voice-summary"),
    }
