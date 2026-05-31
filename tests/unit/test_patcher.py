from pathlib import Path

from hermes_slack_ext.core.patcher import apply_board_patch, board_markers_present

FRAG = (
    "    async def send_kanban_board(self):\n"
    "        return 1\n"
)


def _fixture() -> str:
    return Path("tests/fixtures/slack_min.py").read_text()


def test_patch_inserts_all_board_markers():
    out = apply_board_patch(_fixture(), FRAG)
    assert '@self._app.command("/board")' in out
    assert "_board_action_locks" in out
    assert "hermes_board_task_create" in out
    assert "async def send_kanban_board" in out
    assert 'if name != "board"' in out          # exclude board from the generic slash handler
    assert board_markers_present(out)


def test_patch_is_idempotent():
    once = apply_board_patch(_fixture(), FRAG)
    twice = apply_board_patch(once, FRAG)
    assert once == twice


def test_single_bodied_confirm_guard():
    out = apply_board_patch(_fixture(), FRAG)
    assert out.count("async def _handle_slash_confirm_action(") == 1
