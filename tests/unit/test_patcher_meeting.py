import pytest

from hermes_slack_ext.core import patcher as P

_SKELETON = '''\
class SlackAdapter:
    def __init__(self):
        self._slash_command_contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}

    async def connect(self):
            import re as _re

            _slash_names = [name for name, _d, _h in slack_native_slashes()]
            if _slash_names:
                _slash_pattern = _re.compile(r"x")

            for _action_id in ("hermes_confirm_once",):
                self._app.action(_action_id)(self._handle_slash_confirm_action)

            # Start Socket Mode handler in background
            self._handler = None

    async def _handle_slash_confirm_action(self, ack, body, action):
        await ack()
'''

_MEETING_FRAG = "    async def send_meeting_room(self, event):\n        return \"ok\"\n"
_BOARD_FRAG = "    async def send_kanban_board(self, event):\n        return \"ok\"\n"


def test_meeting_patch_inserts_all_markers():
    out = P.apply_meeting_patch(_SKELETON, _MEETING_FRAG)
    assert '@self._app.command("/meeting")' in out
    assert "_meeting_action_locks" in out
    assert "hermes_meeting_new" in out
    assert "send_meeting_room" in out
    assert 'if name not in ("meeting",)' in out or 'name != "meeting"' in out
    assert P.meeting_markers_present(out)


def test_meeting_patch_is_idempotent():
    once = P.apply_meeting_patch(_SKELETON, _MEETING_FRAG)
    twice = P.apply_meeting_patch(once, _MEETING_FRAG)
    assert once == twice


def test_board_then_meeting_excludes_both_slashes():
    board = P.apply_board_patch(_SKELETON, _BOARD_FRAG)
    both = P.apply_meeting_patch(board, _MEETING_FRAG)
    assert '@self._app.command("/board")' in both
    assert '@self._app.command("/meeting")' in both
    assert '"board"' in both and '"meeting"' in both
    assert "send_kanban_board" in both and "send_meeting_room" in both
    P._assert_single_bodied_confirm(both)


def test_meeting_then_board_also_composes():
    meeting = P.apply_meeting_patch(_SKELETON, _MEETING_FRAG)
    both = P.apply_board_patch(meeting, _BOARD_FRAG)
    assert '@self._app.command("/board")' in both
    assert '@self._app.command("/meeting")' in both
    assert "send_kanban_board" in both and "send_meeting_room" in both
