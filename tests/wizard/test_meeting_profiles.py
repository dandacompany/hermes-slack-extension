from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps.meeting_profiles import MeetingProfilesStep


def _ctx(tmp_path, features):
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data["features"] = features
    return ctx


def test_skips_when_no_meeting(tmp_path):
    assert MeetingProfilesStep().should_run(_ctx(tmp_path, ["board"])) is False


def test_default_accept_yields_four_profiles(tmp_path):
    ctx = _ctx(tmp_path, ["meeting"])
    # "default" path: accept the default set of 4 as-is
    prompts = ScriptedPrompts({"profile_mode": ["default"]})
    MeetingProfilesStep().prompt(ctx, prompts)
    profiles = ctx.data["profiles"]
    assert len(profiles) == 4
    assert sum(1 for p in profiles if p["base_app"]) == 1
    # each profile has persona fields (filled in from the preset)
    assert all("persona_display_name" in p for p in profiles)


def test_default_profiles_have_aligned_names(tmp_path):
    ctx = _ctx(tmp_path, ["meeting"])
    MeetingProfilesStep().prompt(ctx, ScriptedPrompts({"profile_mode": ["default"]}))
    mod = next(p for p in ctx.data["profiles"] if p["base_app"])
    assert mod["profile_id"] == "moderator"
    assert mod["persona_display_name"] == "Moderator"


def test_preset_mode_dedupes_colliding_ids(tmp_path):
    # choosing the same preset twice causes a profile_id collision -> disambiguate with a _2 suffix (prevents .env overwrite).
    ctx = _ctx(tmp_path, ["meeting"])
    prompts = ScriptedPrompts({
        "profile_mode": ["preset"], "profile_count": ["2"],
        "preset_0": ["researcher"], "preset_1": ["researcher"],
    })
    MeetingProfilesStep().prompt(ctx, prompts)
    ids = [p["profile_id"] for p in ctx.data["profiles"]]
    assert len(ids) == len(set(ids)), ids
    assert "researcher" in ids and "researcher_2" in ids
