"""TTS voice catalog + per-profile config helpers for the meeting wizard.

Pure functions over ``meeting/tts-voices.yaml``. The wizard's TtsStep uses these
to present provider/voice choices and to build the ``tts`` config block merged
into each profile's ``config.yaml``. The [TTS] send-hook then reads that block
(via Hermes's own tts_tool) to synthesize a profile's spoken text in its voice.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_ASSETS = Path(__file__).resolve().parents[1] / "meeting"


def load_voice_catalog() -> dict:
    return yaml.safe_load((_ASSETS / "tts-voices.yaml").read_text(encoding="utf-8")) or {}


def provider_choices(catalog: dict) -> list[str]:
    """Provider keys in catalog order (what the wizard offers for selection)."""
    return list(catalog.keys())


def provider_label(catalog: dict, provider: str) -> str:
    return catalog.get(provider, {}).get("label", provider)


def voices_for(catalog: dict, provider: str) -> list[dict]:
    """Selectable {value,label} voices for a provider (suggestions only when the
    provider is account_specific)."""
    return list(catalog.get(provider, {}).get("voices", []))


def is_built_in(catalog: dict, provider: str) -> bool:
    return bool(catalog.get(provider, {}).get("built_in"))


def needs_plugin(catalog: dict, provider: str) -> bool:
    return bool(catalog.get(provider, {}).get("needs_plugin"))


def api_key_env(catalog: dict, provider: str) -> str:
    return catalog.get(provider, {}).get("needs_api_key", "") or ""


def pip_package(catalog: dict, provider: str) -> str:
    return catalog.get(provider, {}).get("pip", "") or ""


def build_profile_tts_config(catalog: dict, provider: str, voice: str) -> dict:
    """Config block to merge into a profile's config.yaml.

    Built-in providers use ``tts.<provider>.<config_voice_key>``; non-built-in
    (command/plugin) providers use ``tts.providers.<provider>`` with a
    ``type: command`` shell-template the operator completes. ``voice.auto_tts`` is
    kept false — the meeting speaks selectively via the [TTS] send-hook, not by
    auto-reading every message.
    """
    prov = catalog.get(provider, {})
    key = prov.get("config_voice_key", "voice")
    block: dict = {"voice": {"auto_tts": False}, "tts": {"provider": provider}}
    if needs_plugin(catalog, provider):
        # command-type provider: operator fills in the shell command template.
        entry: dict = {"type": "command", "command": "<TTS_COMMAND_TEMPLATE>", "output_format": "mp3"}
        if voice:
            entry[key] = voice
        block["tts"]["providers"] = {provider: entry}
    else:
        if voice:
            block["tts"][provider] = {key: voice}
    return block
