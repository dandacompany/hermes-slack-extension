from __future__ import annotations
import re as _re_mod

# --- Ported verbatim from install.py lines 30-58 ---
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


# Injection point for Block Kit action handlers inside connect(). Hermes 0.16
# extracted Socket Mode start into ``_start_socket_mode_handler()``, so the old
# inline "Start Socket Mode handler in background" comment is gone. We anchor on
# the adjacent slash-confirm action registration (0.16+) and fall back to the
# pre-0.16 Socket Mode marker, so the extension patches both layouts. Both
# anchors are 12-space indented, matching the action snippets exactly.
_ACTION_INJECT_ANCHORS = (
    "            # Register Block Kit action handlers for slash-confirm buttons\n",  # Hermes 0.16+
    "            # Start Socket Mode handler in background\n",                         # Hermes <= 0.15.1
)


def _action_inject_anchor(text: str) -> str | None:
    return next((a for a in _ACTION_INJECT_ANCHORS if a in text), None)


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

    # Generic-slash exclusion — delegated to a shared helper (composes
    # idempotently regardless of board/meeting install order). Board-only still
    # produces `if name != "board"` as before.
    text = _apply_slash_exclusion(text, "board")

    if "hermes_board_task_create" not in text:
        anchor = _action_inject_anchor(text)
        if anchor is None:
            raise PatchError("missing board action-handler injection anchor")
        text = text.replace(anchor, BOARD_ACTION_SNIPPET + anchor, 1)

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
    # Decided by 4 functional markers. The generic-slash exclusion
    # (`if name != "board"`) is excluded from the check because it is promoted to
    # `if name not in ("board", "meeting")` when meeting is composed, making it
    # unstable here (the exclusion behavior itself is covered by patcher tests).
    return all(m in text for m in (
        "_board_action_locks", '@self._app.command("/board")',
        "hermes_board_task_create", "async def send_kanban_board",
    ))


# --- Meeting splice snippets ---

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

# Outbound send() hook: after the agent response is posted, (re)post the Meeting
# Controls card at the bottom of a channel that has a live meeting so the buttons
# follow the conversation. The call is spliced before send()'s success return.
_SEND_HOOK_CALL = "            await self._maybe_post_meeting_controls(chat_id)\n"
_SEND_RETURN_ANCHOR = (
    "            return SendResult(\n"
    "                success=True,\n"
    "                message_id=sent_ts,\n"
    "                raw_response=last_result,\n"
    "            )\n"
)

# Outbound send() input hook: in a live-meeting channel, strip internal
# scaffolding and convert `@ProfileName` routing into real mentions before the
# agent's text is formatted/posted. The call is spliced before format_message().
_SEND_CLEAN_CALL = "            content = self._maybe_clean_meeting_message(chat_id, content)\n"
# Speak hook: synthesize [TTS]...[/TTS] content with the bot's voice + upload audio,
# then strip the markers. Spliced after the clean call, before format_message.
_SEND_SPEAK_CALL = "            content = await self._maybe_speak_meeting_tts(chat_id, content, reply_to)\n"
_SEND_FORMAT_ANCHOR = (
    "            # Convert standard markdown → Slack mrkdwn\n"
    "            formatted = self.format_message(content)\n"
)


def _apply_slash_exclusion(text: str, name: str) -> str:
    """Exclude `name` from the generic-slash list. (A) one-liner -> `!= name`,
    (B) board's `if name != "X"` -> `("X", "name")` tuple, (C) add to an existing
    tuple. Idempotent."""
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
    """Apply the meeting splices (same structure as the board patch) to slack.py.
    Idempotent regardless of whether the board patch is installed. Raises
    PatchError if an anchor is missing."""
    if "_meeting_action_locks" not in text:
        if _INIT_ANCHOR not in text:
            raise PatchError("slack.py __init__ anchor (_slash_command_contexts) not found")
        text = text.replace(_INIT_ANCHOR, _INIT_ANCHOR + MEETING_LOCK_SNIPPET, 1)

    if '@self._app.command("/meeting")' not in text:
        if _RE_IMPORT_ANCHOR not in text:
            raise PatchError("connect() 'import re as _re' anchor not found")
        text = text.replace(_RE_IMPORT_ANCHOR, _RE_IMPORT_ANCHOR + MEETING_COMMAND_SNIPPET, 1)

    text = _apply_slash_exclusion(text, "meeting")

    if "hermes_meeting_new" not in text:
        anchor = _action_inject_anchor(text)
        if anchor is None:
            raise PatchError("connect() action-handler injection anchor not found")
        text = text.replace(anchor, MEETING_ACTION_SNIPPET + anchor, 1)

    methods = methods_frag.rstrip()
    if _CONFIRM_ANCHOR not in text:
        raise PatchError("methods anchor (_handle_slash_confirm_action) not found")
    if _MEETING_METHODS_START in text:
        start = text.index(_MEETING_METHODS_START)
        end = text.index(_CONFIRM_ANCHOR, start)
        text = text[:start] + methods + "\n\n" + text[end:]
    else:
        text = text.replace(_CONFIRM_ANCHOR, methods + "\n\n" + _CONFIRM_ANCHOR, 1)

    # Splice the outbound send() hook (idempotent via the call presence guard).
    if "self._maybe_post_meeting_controls(chat_id)" not in text:
        if _SEND_RETURN_ANCHOR not in text:
            raise PatchError("send() success-return anchor not found")
        text = text.replace(_SEND_RETURN_ANCHOR, _SEND_HOOK_CALL + _SEND_RETURN_ANCHOR, 1)

    # Input hook: clean/convert meeting messages before they are formatted.
    if "self._maybe_clean_meeting_message(chat_id, content)" not in text:
        if _SEND_FORMAT_ANCHOR not in text:
            raise PatchError("send() format_message anchor not found")
        text = text.replace(_SEND_FORMAT_ANCHOR, _SEND_CLEAN_CALL + _SEND_FORMAT_ANCHOR, 1)

    # Speak hook: synthesize [TTS] content + upload audio (inserted after clean, before format).
    if _SEND_SPEAK_CALL not in text:
        _old_speak = "            content = await self._maybe_speak_meeting_tts(chat_id, content)\n"
        if _old_speak in text:
            text = text.replace(_old_speak, _SEND_SPEAK_CALL, 1)  # migrate the pre-reply_to signature
        else:
            if _SEND_FORMAT_ANCHOR not in text:
                raise PatchError("send() format_message anchor not found")
            text = text.replace(_SEND_FORMAT_ANCHOR, _SEND_SPEAK_CALL + _SEND_FORMAT_ANCHOR, 1)

    _assert_single_bodied_confirm(text)
    return text


def meeting_markers_present(text: str) -> bool:
    return all(m in text for m in (
        "_meeting_action_locks",
        '@self._app.command("/meeting")',
        "hermes_meeting_new",
        _MEETING_METHODS_START.strip(),
    ))
