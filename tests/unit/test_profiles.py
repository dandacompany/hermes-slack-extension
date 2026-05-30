from hermes_slack_ext.core import profiles as P


def test_load_presets_returns_dict_by_id():
    presets = P.load_presets()
    assert "moderator" in presets
    assert presets["moderator"]["persona_display_name"] == "Moderator"


def test_default_profiles_is_four_with_one_base():
    defs = P.default_profiles()
    assert len(defs) == 4
    assert sum(1 for d in defs if d["base_app"]) == 1


def test_render_participant_prompt_substitutes_persona():
    persona = {
        "persona_display_name": "Researcher", "role_job": "Researcher",
        "personality_traits": "evidence-driven", "values_and_priorities": "rigor",
        "speaking_style": "concise", "background_context": "market research",
        "decision_lens": "is the claim supported", "avoided_behaviors": "hand-waving",
    }
    out = P.render_participant_prompt(persona, moderator_name="Moderator", role="Researcher")
    assert "<PERSONA_NAME>" not in out
    assert "Researcher" in out
    assert "Moderator" in out


def test_build_allowed_users_includes_all_bots():
    val = P.build_allowed_users("Uhuman", ["Bmod", "Bp1", "Bp2"])
    assert val == "Uhuman,Bmod,Bp1,Bp2"


def test_build_allowed_users_drops_empty_and_dupes():
    # 빈 human → leading comma 없이, 중복 봇은 1회만.
    val = P.build_allowed_users("", ["Bmod", "", "Bp1", "Bmod"])
    assert val == "Bmod,Bp1"
    assert not val.startswith(",")
