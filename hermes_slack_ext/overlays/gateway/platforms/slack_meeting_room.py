"""Block Kit /meeting room runtime (Hermes gateway overlay).

A collection of pure functions called by slack_meeting_methods.pyfrag, which is
spliced into slack.py. Session metadata is persisted to a JSON file kept
separate from normal Slack message sessions.
UI/action spec: hermes-slack-meeting-room references/block-kit-meeting-ui.md.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path

ACTION_PREFIX = "hermes_meeting_"

MODE_OPTIONS = ["mixed", "sequential", "parallel", "directed"]
ROUTING_OPTIONS = ["auto", "manual"]
VOICE_OPTIONS = ["voice-summary", "text-only", "voice-full", "hybrid"]
STATUS_LABELS = {"setup": "Setup", "review": "Review", "active": "Active", "ended": "Ended"}

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
        # Left empty: meeting replies post to the channel root (no thread). A
        # synthetic thread_id makes Slack replies fail with invalid_thread_ts,
        # so we keep this empty and let responses land in the channel body.
        "session_thread_id": "",
    }
    store["meetings"][meeting_id] = meeting
    store["current"][f"{channel_id}:{user_id}"] = meeting_id
    return meeting_id, store


def set_session_thread(store: dict, meeting_id: str, thread_ts: str) -> dict:
    """Pin a meeting's dedicated session thread to a real Slack message ts. This
    ts is used both for (a) the Slack reply thread and (b) separating the agent
    session key from normal @mention sessions."""
    m = get_meeting(store, meeting_id)
    if m is not None:
        m["session_thread_id"] = thread_ts
    return store


def build_room_anchor_text(meeting: dict) -> str:
    """Meeting-start header posted to the channel body (so the meeting
    conversation and notes stay visible in the channel)."""
    parts = ", ".join(meeting.get("participants", [])) or "—"
    return (f":clipboard: *Meeting started — {meeting.get('title', '(untitled)')}*\n"
            f"Participants: {parts}\n_This meeting runs in this channel._")


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


# ----- Action-value codec (button value JSON; self-contained meeting_id) -----

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


# ----- Auto-routing: profile-name -> real Slack mention + scaffolding cleanup -----

def mention_map_path() -> Path:
    return _hermes_home() / "hermes-slack-ext" / "meeting_mentions.json"


def load_mention_map() -> dict:
    """Profile display name -> Slack user id (e.g. {"Researcher": "U123"}). Written
    at install (wireup) so the moderator's gateway can turn `@Researcher` routing
    into a real mention that actually pings the participant bot."""
    p = mention_map_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


_MEETING_BLOCK_RE = re.compile(r"\n*\[MEETING\].*?\[/MEETING\]\n*", re.DOTALL)
_PARALLEL_DONE_RE = re.compile(r"(?m)^\s*\[PARALLEL-DONE\]\s*$\n?")


def strip_meeting_scaffolding(text: str) -> str:
    """Remove internal scaffolding the moderator/participants emit that end users
    should not see: the [MEETING] state block and [PARALLEL-DONE] markers. Routing
    addresses (`@Name`) are kept — they carry the hand-off and become real mentions.
    SKILL.md is also simplified to not emit these; this is a defensive net."""
    if not text:
        return text
    text = _MEETING_BLOCK_RE.sub("\n", text)
    text = _PARALLEL_DONE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def apply_meeting_mentions(text: str, name_to_id: dict) -> str:
    """Convert `@<ProfileName>` tokens (for known profiles) into real Slack
    mentions `<@id>` so routing/hand-off actually pings the target bot. Only known
    profile names are converted, longest first to avoid partial matches."""
    if not text or not name_to_id:
        return text
    for name in sorted(name_to_id, key=len, reverse=True):
        uid = name_to_id.get(name)
        if not uid:
            continue
        text = re.sub(r"@" + re.escape(name) + r"\b", f"<@{uid}>", text)
    return text


def clean_meeting_message(text: str, name_to_id: dict) -> str:
    """Outbound pipeline for messages in an active meeting channel: drop
    scaffolding, then convert `@Name` routing into real mentions."""
    return apply_meeting_mentions(strip_meeting_scaffolding(text), name_to_id)


# ----- Prompt Contract builders (block-kit-meeting-ui.md) -----

_SESSION_NOTE = (
    "Session: this is a dedicated meeting session created from the Slack Block Kit "
    "`/meeting` UI. Keep it separate from normal @mention conversations. "
    "Start / Continue / End / Next-speaker selection are accepted ONLY via the "
    "*Meeting Controls* card buttons in the channel (the user does not need to re-type "
    "a slash command). Show the setup draft first and do not @mention participants yet. "
    "Respond in the language of the meeting topic and participants."
)


def build_start_prompt(meeting: dict) -> str:
    parts = ", ".join(meeting.get("participants", []))
    # A header starting with "/" is re-parsed by the gateway as a slash command
    # (regardless of message_type), so deliver the setup signal without a
    # leading slash.
    return (
        f"Meeting setup — Topic: {meeting.get('title', '')}\n\n"
        f"Participants: {parts}\n"
        f"Turns: {meeting.get('turns', '')}\n"
        f"Mode: {meeting.get('mode', '')}\n"
        f"Routing: {meeting.get('routing_mode', '')}\n"
        f"Voice: {meeting.get('voice_mode', '')}\n"
        f"{_SESSION_NOTE}"
    )


def build_continue_prompt(meeting: dict, text: str) -> str:
    return text.strip()


def build_next_prompt(meeting: dict, profile: str) -> str:
    return (
        f"It is {profile}'s turn (1 turn). "
        f"Manual routing: ask only {profile} to speak this turn; "
        f"do not call any other participant."
    )


def build_end_prompt(meeting: dict) -> str:
    return (
        "End the meeting. Summarize the discussion so far focusing on decisions and "
        "action items, list any remaining open issues, and finalize. Do not call any "
        "additional participants."
    )


def build_approve_prompt(meeting: dict) -> str:
    # Approval signal after the setup draft is shown. The skill interprets a short
    # approval as "start the meeting from the existing state" (do not reprint the
    # setup draft). Re-sending the full setup prompt would make the moderator draft
    # again (a duplicate draft), so here we convey approval intent only.
    routing = meeting.get("routing_mode", "auto")
    if routing == "manual":
        tail = "Routing is manual. Wait until the user selects the next speaker in the UI."
    else:
        tail = "Routing is auto. Immediately route to the first speaker (call exactly one participant)."
    return (
        "Approved. Start the meeting using the setup draft above. "
        "Do not print the setup draft again — proceed directly. " + tail
    )


# ----- Block Kit renderers -----

def _btn(text: str, action_id: str, value: str, *, style: str | None = None) -> dict:
    el = {"type": "button", "text": {"type": "plain_text", "text": text}, "action_id": action_id}
    if value:
        el["value"] = value
    if style:
        el["style"] = style
    return el


def meeting_control_elements(meeting: dict) -> list:
    """Status-aware list of action blocks (shared by the creation card, the room,
    and the controls appended below responses).
    - setup:  [Start]  Continue  End            (show the draft)
    - review: [Approve]  Continue  End           (approve draft -> start routing; both = start action)
    - active: Continue  End  (+ Next:{participant} when manual)
    - ended:  no buttons
    'Start' and 'Approve' use the same start action; the handler branches on status."""
    mid = meeting["id"]
    status = meeting.get("status", "")
    base = []
    if status == "setup":
        base.append(_btn("Start", f"{ACTION_PREFIX}start", action_value(mid, "start"), style="primary"))
    elif status == "review":
        base.append(_btn("Approve", f"{ACTION_PREFIX}start", action_value(mid, "start"), style="primary"))
    if status != "ended":
        base.append(_btn("Continue", f"{ACTION_PREFIX}continue_open", action_value(mid, "continue")))
        base.append(_btn("End", f"{ACTION_PREFIX}end", action_value(mid, "end"), style="danger"))
    blocks = []
    if base:
        blocks.append({"type": "actions", "block_id": f"meeting-act-{mid}", "elements": base})
    # Manual routing while active: one Next button per participant (a separate
    # actions block — Slack allows up to 25 elements per block).
    if status == "active" and meeting.get("routing_mode") == "manual":
        next_btns = [
            _btn(f"Next: {p}", f"{ACTION_PREFIX}next", action_value(mid, "next", profile=p))
            for p in meeting.get("participants", [])[:24]
        ]
        if next_btns:
            blocks.append({"type": "actions", "block_id": f"meeting-next-{mid}", "elements": next_btns})
    return blocks


def _meeting_row_blocks(meeting: dict) -> list:
    mid = meeting["id"]
    status = STATUS_LABELS.get(meeting.get("status", ""), meeting.get("status", ""))
    parts = ", ".join(meeting.get("participants", [])) or "—"
    section = {
        "type": "section",
        "block_id": f"meeting-{mid}",
        "text": {"type": "mrkdwn",
                 "text": f"*{meeting.get('title', '(untitled)')}*  ·  _{status}_\nParticipants: {parts}"},
    }
    return [section, *meeting_control_elements(meeting)]


def build_meeting_card_blocks(meeting: dict) -> tuple:
    """Single-meeting in-channel control card. Exposes the action buttons
    (Start/Approve/Continue/End/Next) in the channel body so the user controls the
    meeting where the conversation flows without re-invoking a slash command.

    While `awaiting` is set (a button was pressed and the moderator's async reply
    has not arrived yet), the card shows a "responding…" state with NO action
    buttons — the buttons reappear only once the reply is posted (the send() hook
    re-posts this card below the reply). This prevents the user from pressing the
    next button before the answer is visible. The /meeting room launcher is not
    gated this way, so it remains a recovery path."""
    mid = meeting["id"]
    title = meeting.get("title", "(untitled)")
    status = STATUS_LABELS.get(meeting.get("status", ""), meeting.get("status", ""))
    parts = ", ".join(meeting.get("participants", [])) or "—"
    awaiting = bool(meeting.get("awaiting"))
    ctx_text = (":hourglass_flowing_sand: *Meeting Controls* — the moderator is responding; "
                "controls appear below the reply."
                if awaiting else ":clipboard: *Meeting Controls* — use the buttons below.")
    blocks = [
        {"type": "context", "elements": [{"type": "mrkdwn", "text": ctx_text}]},
        {"type": "section", "block_id": f"meeting-{mid}",
         "text": {"type": "mrkdwn",
                  "text": f"*{title}*  ·  _{status}_\nParticipants: {parts}"}},
    ]
    if not awaiting:
        blocks.extend(meeting_control_elements(meeting))
    return f"Meeting Controls — {title}", blocks


def build_meeting_room_blocks(store: dict, channel_id: str) -> tuple:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Hermes Meeting Room"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": "Meeting sessions are controlled only via this UI and kept separate from normal @mention chats."}]},
        {"type": "actions", "elements": [
            _btn("New meeting", f"{ACTION_PREFIX}new_open", "", style="primary"),
            _btn("Refresh", f"{ACTION_PREFIX}refresh", ""),
        ]},
        {"type": "divider"},
    ]
    rows = list_meetings(store, channel_id)
    if not rows:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": "_No meetings yet. Press `New meeting`._"}]})
    for m in rows:
        row = _meeting_row_blocks(m)
        if len(blocks) + len(row) > _MAX_BLOCKS:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": "_Meetings beyond the display limit are omitted._"}]})
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
                                "placeholder": {"type": "plain_text", "text": "Comma-separated"}}
    return {
        "type": "modal", "callback_id": f"{ACTION_PREFIX}new",
        "private_metadata": json.dumps({"channel_id": channel_id, "user_id": user_id}),
        "title": {"type": "plain_text", "text": "New meeting"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {"type": "input", "block_id": "topic", "label": {"type": "plain_text", "text": "Topic & goal"},
             "element": {"type": "plain_text_input", "action_id": "v"}},
            {"type": "input", "block_id": "participants",
             "label": {"type": "plain_text", "text": "Participants"}, "element": participants_element},
            {"type": "input", "block_id": "turns", "label": {"type": "plain_text", "text": "Turns"},
             "element": {"type": "plain_text_input", "action_id": "v", "initial_value": "4"}},
            _select_input("mode", "Mode", MODE_OPTIONS, "mixed"),
            _select_input("routing", "Routing", ROUTING_OPTIONS, "auto"),
            _select_input("voice", "Voice", VOICE_OPTIONS, "voice-summary"),
        ],
    }


def continue_modal_view(meeting_id: str) -> dict:
    return {
        "type": "modal", "callback_id": f"{ACTION_PREFIX}continue", "private_metadata": meeting_id,
        "title": {"type": "plain_text", "text": "Continue"},
        "submit": {"type": "plain_text", "text": "Send"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [{"type": "input", "block_id": "msg",
                    "label": {"type": "plain_text", "text": "Message"},
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
