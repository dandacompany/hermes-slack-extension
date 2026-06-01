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
    assert sum(1 for d in defaults if d.get("base_app")) == 1  # only the moderator is base_app
    for d in defaults:
        assert d["preset"] in cat_ids, f"{d['preset']} not in preset catalog"


def test_tts_voices_catalog_is_well_formed():
    cat = _load("tts-voices.yaml")
    # the wizard's 6 selectable providers
    assert set(cat) == {"edge", "openai", "gemini", "elevenlabs", "typecast", "supertonic"}
    # built-ins vs plugin-only
    assert cat["edge"]["built_in"] and cat["openai"]["built_in"] and cat["gemini"]["built_in"]
    assert cat["elevenlabs"]["built_in"]
    assert not cat["typecast"]["built_in"] and cat["typecast"]["needs_plugin"]
    assert not cat["supertonic"]["built_in"] and cat["supertonic"]["needs_plugin"]
    # fixed-list providers carry selectable voices with value+label
    for p in ("edge", "openai", "gemini"):
        assert cat[p]["voices"], f"{p} has no voices"
        for v in cat[p]["voices"]:
            assert v.get("value") and v.get("label")
    # config voice keys differ by provider shape
    assert cat["edge"]["config_voice_key"] == "voice"
    assert cat["elevenlabs"]["config_voice_key"] == "voice_id"
    # account-specific providers are flagged so the wizard fetches/prompts a voice id
    assert cat["elevenlabs"]["account_specific"] and cat["typecast"]["account_specific"]


def test_edge_voices_are_real_korean_edge_tts_voices():
    # edge-tts (the free endpoint) serves only a subset of Azure's catalog. Listing
    # an Azure-only voice makes synthesis fail silently (NoAudioReceived), which is
    # exactly what made the Designer bot go silent. The wizard cycles this list
    # round-robin across profiles, so it must hold ONLY the three real ko-KR edge
    # voices: no Azure-only names (silent failure) and no foreign-locale voices
    # (which would read Korean with the wrong accent when the cycle wraps).
    edge = _load("tts-voices.yaml")["edge"]
    values = {v["value"] for v in edge["voices"]}
    assert values == {
        "ko-KR-SunHiNeural",
        "ko-KR-InJoonNeural",
        "ko-KR-HyunsuMultilingualNeural",
    }, f"edge voices must be exactly the 3 real ko-KR edge-tts voices, got {values}"
    azure_only = {
        "ko-KR-BongJinNeural", "ko-KR-GookMinNeural", "ko-KR-JiMinNeural",
        "ko-KR-SeoHyeonNeural", "ko-KR-SoonBokNeural", "ko-KR-YuJinNeural",
    }
    assert not (values & azure_only), f"Azure-only voices not served by edge-tts: {values & azure_only}"


def test_channel_prompts_have_both_templates():
    cp = _load("channel-prompts.yaml")
    assert "manager_channel_prompt" in cp
    assert "participant_channel_prompt" in cp
    assert "<PERSONA_NAME>" in cp["participant_channel_prompt"]


def test_channel_prompts_use_at_routing_without_scaffolding():
    cp = _load("channel-prompts.yaml")
    mgr = cp["manager_channel_prompt"]
    par = cp["participant_channel_prompt"]
    # Moderator routes by @<ProfileName>; participant hands back with @<MODERATOR_NAME>.
    assert "@<ProfileName>" in mgr
    assert "@<MODERATOR_NAME>" in par
    # No mandated machine scaffolding: no [MEETING] state-block template, and the
    # hand-off is a natural mention rather than a "handoff:" label.
    assert "[/MEETING]" not in mgr
    assert "handoff: @" not in par
