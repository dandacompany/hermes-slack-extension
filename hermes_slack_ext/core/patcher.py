from __future__ import annotations
import re as _re_mod

# --- install.py 라인 30-58에서 그대로 포팅 ---
BOARD_COMMAND_SNIPPET = '''\
            @self._app.command("/board")
            async def handle_board_command(ack, command):
                await ack(
                    response_type="ephemeral",
                    text="Opening Kanban board...",
                )
                logger.info("[Slack] Received /board command from %s in %s", command.get("user_id"), command.get("channel_id"))
                asyncio.create_task(self._handle_board_slash_background(dict(command)))

'''

BOARD_ACTION_SNIPPET = '''\
            # Register Block Kit action handlers for the Slack Kanban board.
            self._app.action(_re.compile(r"^hermes_board_"))(self._handle_board_action)
            self._app.view("hermes_board_task_create")(self._handle_board_create_view)
            self._app.view("hermes_board_task_move")(self._handle_board_move_view)
            self._app.view("hermes_board_task_detail")(self._handle_board_detail_view)
            self._app.view("hermes_board_task_request_changes")(self._handle_board_request_changes_view)

'''

LOCK_SNIPPET = '''\
        # Kanban board message locks: prevent repeated clicks from executing
        # multiple mutations while Slack is still repainting the message.
        self._board_action_locks: Dict[str, float] = {}
'''


class PatchError(RuntimeError):
    pass


def _assert_single_bodied_confirm(text: str) -> None:
    needle = "async def _handle_slash_confirm_action("
    count = text.count(needle)
    if count != 1:
        raise PatchError(
            f"patched slack.py has {count} _handle_slash_confirm_action definitions (expected 1)"
        )
    lines = text.splitlines()
    idx = next(i for i, line in enumerate(lines) if needle in line)
    sig_indent = len(lines[idx]) - len(lines[idx].lstrip())
    next_code = next((line for line in lines[idx + 1:] if line.strip()), "")
    if len(next_code) - len(next_code.lstrip()) <= sig_indent:
        raise PatchError("body-less _handle_slash_confirm_action signature after splice")


def apply_board_patch(text: str, methods_frag: str) -> str:
    """Idempotently splice the board /board command, action handlers, lock map,
    generic-slash exclusion, and helper methods into slack.py source text.
    Ported from hermes-slack-board/scripts/install.py:patch_slack_py."""
    if "_board_action_locks" not in text:
        marker = "        self._slash_command_contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}\n"
        if marker not in text:
            raise PatchError("missing slash-command context marker")
        text = text.replace(marker, marker + LOCK_SNIPPET, 1)

    if '@self._app.command("/board")' not in text:
        marker = "            import re as _re\n\n"
        if marker not in text:
            raise PatchError("missing command registration import marker")
        text = text.replace(marker, marker + BOARD_COMMAND_SNIPPET, 1)

    single_line = "            _slash_names = [name for name, _d, _h in slack_native_slashes()]\n"
    filtered = (
        "            _slash_names = [\n"
        "                name for name, _d, _h in slack_native_slashes()\n"
        '                if name != "board"\n'
        "            ]\n"
    )
    if single_line in text:
        text = text.replace(single_line, filtered, 1)

    if "hermes_board_task_create" not in text:
        marker = "            # Start Socket Mode handler in background\n"
        if marker not in text:
            raise PatchError("missing Socket Mode start marker")
        text = text.replace(marker, BOARD_ACTION_SNIPPET + marker, 1)

    methods = methods_frag.rstrip()
    methods_start = "    async def send_kanban_board"
    methods_end = "    async def _handle_slash_confirm_action"
    if methods_end not in text:
        raise PatchError("missing slash confirm handler insertion marker")
    if methods_start in text:
        start = text.index(methods_start)
        end = text.index(methods_end, start)
        text = text[:start] + methods + "\n\n" + text[end:]
    else:
        text = text.replace(methods_end, methods + "\n\n" + methods_end, 1)

    _assert_single_bodied_confirm(text)
    return text


def board_markers_present(text: str) -> bool:
    return all(m in text for m in (
        "_board_action_locks", '@self._app.command("/board")',
        "hermes_board_task_create", 'if name != "board"', "async def send_kanban_board",
    ))


# --- 미팅 splice 스니펫 ---

MEETING_LOCK_SNIPPET = (
    "        self._meeting_action_locks: Dict[str, float] = {}\n"
)

MEETING_COMMAND_SNIPPET = '''\
            @self._app.command("/meeting")
            async def handle_meeting_command(ack, command):
                await ack(response_type="ephemeral", text="Opening meeting room...")
                asyncio.create_task(self._handle_meeting_slash_background(dict(command)))

'''

MEETING_ACTION_SNIPPET = '''\
            self._app.action(_re.compile(r"^hermes_meeting_"))(self._handle_meeting_action)
            self._app.view("hermes_meeting_new")(self._handle_meeting_new_view)
            self._app.view("hermes_meeting_continue")(self._handle_meeting_continue_view)
'''

_INIT_ANCHOR = (
    "        self._slash_command_contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}\n"
)
_RE_IMPORT_ANCHOR = "            import re as _re\n\n"
_SOCKET_ANCHOR = "            # Start Socket Mode handler in background\n"
_CONFIRM_ANCHOR = "    async def _handle_slash_confirm_action"
_MEETING_METHODS_START = "    async def send_meeting_room"


def _apply_slash_exclusion(text: str, name: str) -> str:
    """generic-slash 목록에서 name을 제외한다. (A) one-liner→`!= name`,
    (B) board의 `if name != "X"`→`("X","name")` 튜플, (C) 기존 튜플에 추가. 멱등."""
    one_liner = "            _slash_names = [name for name, _d, _h in slack_native_slashes()]\n"
    if one_liner in text:
        repl = (
            "            _slash_names = [\n"
            "                name for name, _d, _h in slack_native_slashes()\n"
            f'                if name != "{name}"\n'
            "            ]\n"
        )
        return text.replace(one_liner, repl, 1)
    m = _re_mod.search(r'                if name != "([^"]+)"\n', text)
    if m:
        other = m.group(1)
        if other == name:
            return text
        new_line = f'                if name not in ("{other}", "{name}")\n'
        return text[:m.start()] + new_line + text[m.end():]
    m2 = _re_mod.search(r'if name not in \(([^)]*)\)', text)
    if m2:
        existing = set(_re_mod.findall(r'"([^"]+)"', m2.group(1)))
        if name in existing:
            return text
        existing.add(name)
        new_tuple = ", ".join(f'"{n}"' for n in sorted(existing))
        return text[:m2.start(1)] + new_tuple + text[m2.end(1):]
    return text


def apply_meeting_patch(text: str, methods_frag: str) -> str:
    """보드 patch와 동일 구조의 5-splice를 미팅용으로 적용한다. 보드 설치 여부와
    무관하게 멱등. 마커가 없으면 PatchError."""
    if "_meeting_action_locks" not in text:
        if _INIT_ANCHOR not in text:
            raise PatchError("slack.py __init__ 앵커(_slash_command_contexts)를 찾지 못함")
        text = text.replace(_INIT_ANCHOR, _INIT_ANCHOR + MEETING_LOCK_SNIPPET, 1)

    if '@self._app.command("/meeting")' not in text:
        if _RE_IMPORT_ANCHOR not in text:
            raise PatchError("connect()의 'import re as _re' 앵커를 찾지 못함")
        text = text.replace(_RE_IMPORT_ANCHOR, _RE_IMPORT_ANCHOR + MEETING_COMMAND_SNIPPET, 1)

    text = _apply_slash_exclusion(text, "meeting")

    if "hermes_meeting_new" not in text:
        if _SOCKET_ANCHOR not in text:
            raise PatchError("connect()의 'Start Socket Mode' 앵커를 찾지 못함")
        text = text.replace(_SOCKET_ANCHOR, MEETING_ACTION_SNIPPET + _SOCKET_ANCHOR, 1)

    methods = methods_frag.rstrip()
    if _CONFIRM_ANCHOR not in text:
        raise PatchError("methods 앵커(_handle_slash_confirm_action)를 찾지 못함")
    if _MEETING_METHODS_START in text:
        start = text.index(_MEETING_METHODS_START)
        end = text.index(_CONFIRM_ANCHOR, start)
        text = text[:start] + methods + "\n\n" + text[end:]
    else:
        text = text.replace(_CONFIRM_ANCHOR, methods + "\n\n" + _CONFIRM_ANCHOR, 1)

    _assert_single_bodied_confirm(text)
    return text


def meeting_markers_present(text: str) -> bool:
    return all(m in text for m in (
        "_meeting_action_locks",
        '@self._app.command("/meeting")',
        "hermes_meeting_new",
        _MEETING_METHODS_START.strip(),
    ))
