import importlib.util
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
    assert m["session_thread_id"] == "meeting:C1:mtg-x"
    assert m["status"] == "setup"
    assert m["participants"] == ["Researcher", "Designer"]
    assert m["routing_mode"] == "manual"
    assert store["current"]["C1:U1"] == "mtg-x"


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
