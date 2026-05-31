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

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        try:
            # Convert standard markdown → Slack mrkdwn
            formatted = self.format_message(content)
            last_result = None
            sent_ts = None
            return SendResult(
                success=True,
                message_id=sent_ts,
                raw_response=last_result,
            )
        except Exception as e:
            return SendResult(success=False, error=str(e))

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


def test_meeting_patch_splices_send_controls_hook():
    # The outbound send() hook must be inserted before send()'s success return so
    # the Meeting Controls card follows the conversation.
    out = P.apply_meeting_patch(_SKELETON, _MEETING_FRAG)
    assert "await self._maybe_post_meeting_controls(chat_id)" in out
    hook = out.index("await self._maybe_post_meeting_controls(chat_id)")
    ret = out.index("return SendResult(\n                success=True,", hook)
    assert ret > hook  # the call precedes the success return


def test_meeting_patch_splices_send_clean_hook():
    # The input hook must clean/convert the message before format_message() so
    # @ProfileName routing becomes a real mention and scaffolding is stripped.
    out = P.apply_meeting_patch(_SKELETON, _MEETING_FRAG)
    assert "content = self._maybe_clean_meeting_message(chat_id, content)" in out
    clean = out.index("self._maybe_clean_meeting_message(chat_id, content)")
    fmt = out.index("formatted = self.format_message(content)", clean)
    assert fmt > clean  # the clean call precedes format_message


def test_meeting_patch_raises_without_send_anchor():
    # If slack.py's send() success-return shape changes, fail loudly rather than
    # silently dropping the buttons-on-response hook.
    skeleton_no_send = _SKELETON.replace(
        "            return SendResult(\n"
        "                success=True,\n"
        "                message_id=sent_ts,\n"
        "                raw_response=last_result,\n"
        "            )\n",
        "            return None\n",
    )
    with pytest.raises(P.PatchError):
        P.apply_meeting_patch(skeleton_no_send, _MEETING_FRAG)


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
    import re
    meeting = P.apply_meeting_patch(_SKELETON, _MEETING_FRAG)
    both = P.apply_board_patch(meeting, _BOARD_FRAG)
    assert '@self._app.command("/board")' in both
    assert '@self._app.command("/meeting")' in both
    assert "send_kanban_board" in both and "send_meeting_room" in both
    # Both slashes must be excluded from the generic catch-all (order-independent
    # composition); otherwise /board double-dispatches via generic + dedicated.
    m = re.search(r'if name not in \(([^)]*)\)', both)
    assert m, "generic-slash exclusion is not a tuple — board not excluded"
    names = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert {"board", "meeting"} <= names, f"exclusion set missing board/meeting: {names}"


def test_board_then_meeting_exclusion_is_tuple_of_both():
    import re
    board = P.apply_board_patch(_SKELETON, _BOARD_FRAG)
    both = P.apply_meeting_patch(board, _MEETING_FRAG)
    m = re.search(r'if name not in \(([^)]*)\)', both)
    assert m
    names = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert {"board", "meeting"} <= names


def test_board_markers_present_survives_meeting_composition():
    # board_markers_present must stay True after board+meeting composition
    # (the 4 functional markers persist even when the slash exclusion is promoted
    # to a tuple — prevents a doctor false negative).
    board = P.apply_board_patch(_SKELETON, _BOARD_FRAG)
    both = P.apply_meeting_patch(board, _MEETING_FRAG)
    assert P.board_markers_present(both) is True
    assert P.meeting_markers_present(both) is True
