import importlib.util
import json
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parents[1] / "gateway" / "platforms" / "slack_meeting_room.py"
spec = importlib.util.spec_from_file_location("slack_meeting_room", _MOD)
mr = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mr)
    _LOADED = True
except Exception:
    _LOADED = False

pytestmark = pytest.mark.skipif(not _LOADED, reason="slack_meeting_room import 실패")


def _store_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path / "hermes-slack-ext" / "meeting_sessions.json"


def test_empty_store_roundtrip(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = mr.load_store()
    assert store == {"version": 1, "meetings": {}, "current": {}}
    mr.save_store(store)
    assert mr.load_store() == store


def test_create_meeting_sets_fields_and_thread_id(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = mr.load_store()
    mid, store = mr.create_meeting(
        store, channel_id="C1", user_id="U1", title="YT 기획",
        participants=["Researcher", "Designer"], turns="4", mode="mixed",
        routing_mode="manual", voice_mode="voice-summary", meeting_id="mtg-x",
    )
    m = mr.get_meeting(store, mid)
    assert mid == "mtg-x"
    assert m["session_thread_id"] == ""   # 런타임에 실제 Slack ts로 설정됨
    assert m["status"] == "setup"
    assert m["participants"] == ["Researcher", "Designer"]
    assert m["routing_mode"] == "manual"
    assert store["current"]["C1:U1"] == "mtg-x"


def test_set_session_thread_anchors_real_ts(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = mr.load_store()
    mid, store = mr.create_meeting(
        store, channel_id="C1", user_id="U1", title="t", participants=[],
        turns="3", mode="mixed", routing_mode="auto", voice_mode="text-only", meeting_id="m1")
    store = mr.set_session_thread(store, mid, "1717146402.000100")
    assert mr.get_meeting(store, mid)["session_thread_id"] == "1717146402.000100"


def test_build_room_anchor_text_has_title_and_participants():
    m = {"title": "YT 기획", "participants": ["Researcher", "Designer"]}
    txt = mr.build_room_anchor_text(m)
    assert "YT 기획" in txt and "Researcher" in txt and "Designer" in txt


def test_list_meetings_filters_by_channel(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = {"version": 1, "meetings": {
        "a": {"id": "a", "channel_id": "C1", "status": "setup", "user_id": "U1"},
        "b": {"id": "b", "channel_id": "C2", "status": "active", "user_id": "U1"},
    }, "current": {}}
    rows = mr.list_meetings(store, "C1")
    assert [m["id"] for m in rows] == ["a"]


def test_set_status_persists(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = mr.load_store()
    mid, store = mr.create_meeting(
        store, channel_id="C1", user_id="U1", title="t", participants=[],
        turns="3", mode="mixed", routing_mode="auto", voice_mode="text-only",
        meeting_id="m1")
    store = mr.set_status(store, mid, "active")
    assert mr.get_meeting(store, mid)["status"] == "active"


def test_gen_meeting_id_is_stable_for_clock():
    assert mr.gen_meeting_id(1_700_000_000.0).startswith("mtg-")


def test_action_value_roundtrip():
    v = mr.action_value("mtg-x", "start")
    parsed = mr.parse_action_value(v)
    assert parsed["meeting_id"] == "mtg-x"
    assert parsed["action"] == "start"


def test_action_value_carries_profile():
    v = mr.action_value("mtg-x", "next", profile="Researcher")
    assert mr.parse_action_value(v)["profile"] == "Researcher"


def _meeting():
    return {"id": "mtg-x", "channel_id": "C1", "user_id": "U1", "title": "YT 기획",
            "participants": ["Researcher", "Designer"], "turns": "4", "mode": "mixed",
            "routing_mode": "auto", "voice_mode": "voice-summary",
            "session_thread_id": "meeting:C1:mtg-x", "status": "setup"}


def test_build_start_prompt_follows_contract():
    text = mr.build_start_prompt(_meeting())
    assert text.startswith("/meeting YT 기획")
    assert "참석자: Researcher, Designer" in text
    assert "턴수: 4턴" in text
    assert "진행: mixed" in text
    assert "진행 제어: auto" in text
    assert "음성: voice-summary" in text
    assert "전용 meeting 세션" in text


def test_build_continue_and_next_and_end():
    m = _meeting()
    assert "follow up" in mr.build_continue_prompt(m, "follow up")
    nxt = mr.build_next_prompt(m, "Researcher")
    assert "Researcher" in nxt
    assert "종료" in mr.build_end_prompt(m) or "finaliz" in mr.build_end_prompt(m).lower()


def test_room_blocks_have_header_and_primary_actions(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = {"version": 1, "meetings": {}, "current": {}}
    fallback, blocks = mr.build_meeting_room_blocks(store, "C1")
    assert "Meeting Room" in fallback
    assert blocks[0]["type"] == "header"
    actions = [b for b in blocks if b["type"] == "actions"]
    ids = [e["action_id"] for b in actions for e in b["elements"]]
    assert f"{mr.ACTION_PREFIX}new_open" in ids
    assert f"{mr.ACTION_PREFIX}refresh" in ids


def test_room_blocks_render_meeting_rows_with_actions(tmp_path, monkeypatch):
    _store_path(tmp_path, monkeypatch)
    store = {"version": 1, "meetings": {
        "mtg-x": {"id": "mtg-x", "channel_id": "C1", "user_id": "U1", "title": "YT",
                  "participants": ["Researcher"], "status": "setup",
                  "routing_mode": "manual", "session_thread_id": "meeting:C1:mtg-x"}},
        "current": {}}
    _f, blocks = mr.build_meeting_room_blocks(store, "C1")
    ids = [e["action_id"] for b in blocks if b["type"] == "actions" for e in b["elements"]]
    assert f"{mr.ACTION_PREFIX}start" in ids
    assert f"{mr.ACTION_PREFIX}continue_open" in ids
    assert f"{mr.ACTION_PREFIX}end" in ids
    assert f"{mr.ACTION_PREFIX}next" in ids


def test_new_meeting_modal_uses_multiselect_when_participants_known():
    view = mr.new_meeting_modal_view("C1", "U1", ["Researcher", "Designer"])
    assert view["callback_id"] == f"{mr.ACTION_PREFIX}new"
    assert view["private_metadata"]
    dump = json.dumps(view)
    assert "multi_static_select" in dump


def test_new_meeting_modal_falls_back_to_text_without_participants():
    view = mr.new_meeting_modal_view("C1", "U1", [])
    dump = json.dumps(view)
    assert "multi_static_select" not in dump
    assert "plain_text_input" in dump


def test_parse_new_meeting_submission_reads_all_fields():
    state = {
        "topic": {"v": {"type": "plain_text_input", "value": "YT 기획"}},
        "participants": {"v": {"type": "multi_static_select",
                               "selected_options": [{"value": "Researcher"}, {"value": "Designer"}]}},
        "turns": {"v": {"type": "plain_text_input", "value": "4"}},
        "mode": {"v": {"type": "static_select", "selected_option": {"value": "mixed"}}},
        "routing": {"v": {"type": "static_select", "selected_option": {"value": "manual"}}},
        "voice": {"v": {"type": "static_select", "selected_option": {"value": "voice-summary"}}},
    }
    out = mr.parse_new_meeting_submission(state)
    assert out["title"] == "YT 기획"
    assert out["participants"] == ["Researcher", "Designer"]
    assert out["turns"] == "4"
    assert out["mode"] == "mixed"
    assert out["routing_mode"] == "manual"
    assert out["voice_mode"] == "voice-summary"


def test_continue_modal_carries_meeting_id():
    view = mr.continue_modal_view("mtg-x")
    assert view["callback_id"] == f"{mr.ACTION_PREFIX}continue"
    assert view["private_metadata"] == "mtg-x"
