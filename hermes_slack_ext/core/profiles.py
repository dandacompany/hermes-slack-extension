from __future__ import annotations

from pathlib import Path

import yaml

_MEETING = Path(__file__).resolve().parents[1] / "meeting"

# Maps <PLACEHOLDER> tokens in participant_channel_prompt to persona fields.
_PARTICIPANT_FIELDS = {
    "<PERSONA_NAME>": "persona_display_name",
    "<ROLE_OR_JOB>": "role_job",
    "<PERSONALITY_TRAITS>": "personality_traits",
    "<VALUES_AND_PRIORITIES>": "values_and_priorities",
    "<SPEAKING_STYLE>": "speaking_style",
    "<BACKGROUND_CONTEXT>": "background_context",
    "<DECISION_LENS>": "decision_lens",
    "<AVOIDED_BEHAVIORS>": "avoided_behaviors",
}


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((_MEETING / name).read_text(encoding="utf-8"))


def load_presets() -> dict[str, dict]:
    cat = _load_yaml("business-persona-presets.yaml")["persona_catalog"]
    return {p["id"]: p for p in cat}


def default_profiles() -> list[dict]:
    return list(_load_yaml("default_profiles.yaml")["default_profiles"])


def channel_prompt_templates() -> dict:
    return _load_yaml("channel-prompts.yaml")


def render_participant_prompt(persona: dict, moderator_name: str, role: str) -> str:
    tpl = channel_prompt_templates()["participant_channel_prompt"]
    tpl = tpl.replace("<MODERATOR_NAME>", moderator_name)
    tpl = tpl.replace("<ROLE_SPECIALIZATION>", role)
    for placeholder, field in _PARTICIPANT_FIELDS.items():
        tpl = tpl.replace(placeholder, str(persona.get(field, "")))
    return tpl


def render_moderator_prompt(participant_mentions: list[str]) -> str:
    tpl = channel_prompt_templates()["manager_channel_prompt"]
    return tpl.replace("<PARTICIPANT_MENTION_LIST>", "\n".join(participant_mentions))


def build_allowed_users(human_user_id: str, bot_user_ids: list[str]) -> str:
    """Comma-joined allow-list. Drops empty ids so a missing human/bot id can't
    inject a leading/embedded comma (which would mis-parse the allow-list)."""
    seen: list[str] = []
    for uid in [human_user_id, *bot_user_ids]:
        if uid and uid not in seen:
            seen.append(uid)
    return ",".join(seen)
