from pathlib import Path

import yaml

MEETING = Path("hermes_slack_ext/meeting")


def _load(name):
    return yaml.safe_load((MEETING / name).read_text(encoding="utf-8"))


def test_presets_have_required_fields():
    cat = _load("business-persona-presets.yaml")["persona_catalog"]
    required = {"id", "persona_display_name", "role_job", "personality_traits",
               "values_and_priorities", "speaking_style", "background_context",
               "decision_lens", "avoided_behaviors"}
    for p in cat:
        assert required <= set(p), f"{p.get('id')} missing fields"


def test_default_profiles_reference_existing_presets():
    cat_ids = {p["id"] for p in _load("business-persona-presets.yaml")["persona_catalog"]}
    defaults = _load("default_profiles.yaml")["default_profiles"]
    assert len(defaults) == 4
    assert sum(1 for d in defaults if d.get("base_app")) == 1  # moderator만 base_app
    for d in defaults:
        assert d["preset"] in cat_ids, f"{d['preset']} not in preset catalog"


def test_channel_prompts_have_both_templates():
    cp = _load("channel-prompts.yaml")
    assert "manager_channel_prompt" in cp
    assert "participant_channel_prompt" in cp
    assert "<PERSONA_NAME>" in cp["participant_channel_prompt"]
