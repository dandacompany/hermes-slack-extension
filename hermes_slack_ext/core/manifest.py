from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from hermes_slack_ext.core.hermes import venv_python

_DEFAULT_URL = "https://hermes-agent.local/slack/commands"

# 추가할 슬래시 엔트리(스펙 부록 A.3)
BOARD_ENTRY = {"command": "/board", "description": "Open the Kanban board UI",
               "usage_hint": "[-p project] [-s status]"}
MEETING_ENTRY = {"command": "/meeting", "description": "Open the meeting room UI",
                 "usage_hint": "[topic]"}
# 기능별 기본 drop (스펙 §8.1)
DEFAULT_DROP = {"board": "footer", "meeting": "sethome"}

# 참가자 최소 봇 스코프(스펙 부록 A.4)
_PARTICIPANT_SCOPES = [
    "app_mentions:read", "chat:write", "channels:history", "channels:read",
    "groups:history", "im:history", "users:read", "files:write",
]


def fetch_full_manifest(hermes_root: Path, name: str, description: str) -> dict:
    """Run `hermes slack manifest` in the installed Hermes venv and parse JSON.
    Always reflects the installed version's COMMAND_REGISTRY."""
    py = venv_python(hermes_root)
    env = {**os.environ, "HERMES_HOME": os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))}
    proc = subprocess.run(
        [str(py), "-m", "hermes_cli.main", "slack", "manifest", "--name", name, "--description", description],
        cwd=str(hermes_root), capture_output=True, text=True, check=True, env=env,
    )
    return json.loads(proc.stdout)


def swap_slashes(manifest: dict, drop: list[str], add: list[dict]) -> dict:
    """Drop named commands and append new entries. Invariant: out count == in
    count when len(drop) == len(add). Reuses the existing entries' url."""
    slashes = manifest["features"]["slash_commands"]
    url = slashes[0]["url"] if slashes else _DEFAULT_URL
    drop_set = {d.lstrip("/") for d in drop}
    kept = [s for s in slashes if s["command"].lstrip("/") not in drop_set]
    existing = {s["command"] for s in kept}
    for entry in add:
        full = {"should_escape": False, "url": url, **entry}
        if full["command"] not in existing:
            kept.append(full)
            existing.add(full["command"])
    return {**manifest, "features": {**manifest["features"], "slash_commands": kept}}


def participant_manifest(persona_name: str) -> dict:
    """Minimal manifest for a participant app: no slash commands, socket mode on."""
    return {
        "_metadata": {"major_version": 1, "minor_version": 1},
        "display_information": {"name": persona_name[:35], "background_color": "#1a1a2e"},
        "features": {
            "bot_user": {"display_name": persona_name[:80], "always_online": True},
            "app_home": {"messages_tab_enabled": True},
        },
        "oauth_config": {"scopes": {"bot": list(_PARTICIPANT_SCOPES)}},
        "settings": {
            "event_subscriptions": {"bot_events": [
                "app_mention", "message.channels", "message.groups", "message.im"]},
            "interactivity": {"is_enabled": True},
            "socket_mode_enabled": True,
        },
    }


def entries_for_features(features: list[str]) -> tuple[list[str], list[dict]]:
    """Return (drop_names, add_entries) for the selected features."""
    add: list[dict] = []
    drop: list[str] = []
    if "board" in features:
        add.append(dict(BOARD_ENTRY)); drop.append(DEFAULT_DROP["board"])
    if "meeting" in features:
        add.append(dict(MEETING_ENTRY)); drop.append(DEFAULT_DROP["meeting"])
    return drop, add
