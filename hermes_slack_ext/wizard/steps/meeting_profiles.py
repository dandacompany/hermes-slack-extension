from __future__ import annotations

from hermes_slack_ext.core import profiles as P
from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts

_PERSONA_FIELDS = [
    "persona_display_name", "role_job", "personality_traits", "values_and_priorities",
    "speaking_style", "background_context", "decision_lens", "avoided_behaviors",
]


def _materialize(profile: dict, presets: dict) -> dict:
    """Build a complete profile dict by filling a default_profiles entry with the preset persona fields."""
    preset = presets.get(profile["preset"], {})
    merged = {
        "profile_id": profile["profile_id"],
        "role": profile.get("role", preset.get("persona_display_name", "")),
        "base_app": bool(profile.get("base_app", False)),
        "slack_app_display_name": preset.get("slack_app_display_name", f"Hermes {profile['profile_id'].title()}"),
    }
    for f in _PERSONA_FIELDS:
        merged[f] = preset.get(f, "")
    return merged


def _ensure_unique_ids(profiles: list[dict]) -> list[dict]:
    """On profile_id collisions, disambiguate with _2, _3 suffixes. profile_id must be
    unique because two profiles with the same id would overwrite each other's token .env
    and channel-prompt files (credential loss)."""
    counts: dict[str, int] = {}
    for prof in profiles:
        pid = prof["profile_id"]
        if pid in counts:
            counts[pid] += 1
            prof["profile_id"] = f"{pid}_{counts[pid]}"
        else:
            counts[pid] = 1
    return profiles


class MeetingProfilesStep(Step):
    id = "meeting_profiles"
    title = "Configure meeting profiles"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        presets = P.load_presets()
        defaults = P.default_profiles()
        mode = prompts.select(
            "profile_mode", "Profile configuration method",
            ["default", "preset", "custom"], default="default",
        )
        if mode == "default":
            ctx.data["profiles"] = _ensure_unique_ids([_materialize(d, presets) for d in defaults])
            return
        # The preset/custom paths ask for the number of profiles and then each profile in turn.
        count = int(prompts.text("profile_count", "Number of participants (excluding moderator)", default="3"))
        profiles = [_materialize(defaults[0], presets)]  # moderator default
        preset_ids = list(presets)
        for i in range(count):
            pid = prompts.select(f"preset_{i}", f"Participant {i+1} preset", preset_ids, default=preset_ids[0])
            prof = _materialize({"profile_id": pid, "preset": pid, "base_app": False}, presets)
            if mode == "custom":
                for f in _PERSONA_FIELDS:
                    prof[f] = prompts.text(f"{pid}_{f}", f"{pid}.{f}", default=str(prof[f]))
                prof["profile_id"] = prompts.text(f"{pid}_profile_id", f"{pid} profile id", default=pid)
            profiles.append(prof)
        ctx.data["profiles"] = _ensure_unique_ids(profiles)
