from __future__ import annotations

from hermes_slack_ext.core import profiles as P
from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts

_PERSONA_FIELDS = [
    "persona_display_name", "role_job", "personality_traits", "values_and_priorities",
    "speaking_style", "background_context", "decision_lens", "avoided_behaviors",
]


def _materialize(profile: dict, presets: dict) -> dict:
    """default_profiles 항목을 프리셋 페르소나 필드로 채운 완전한 프로필 dict로 만든다."""
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
    """profile_id 충돌 시 _2, _3 접미사로 분리한다. 같은 id가 둘이면 토큰 .env와
    채널 프롬프트 파일이 서로 덮어써지므로(자격증명 손실) 반드시 유일해야 한다."""
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
    title = "회의 프로필 구성"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        presets = P.load_presets()
        defaults = P.default_profiles()
        mode = prompts.select(
            "profile_mode", "프로필 구성 방식",
            ["default", "preset", "custom"], default="default",
        )
        if mode == "default":
            ctx.data["profiles"] = _ensure_unique_ids([_materialize(d, presets) for d in defaults])
            return
        # preset/custom 경로는 프로필 수와 각 프로필을 순차로 묻는다.
        count = int(prompts.text("profile_count", "참가자 수(모더레이터 제외)", default="3"))
        profiles = [_materialize(defaults[0], presets)]  # moderator 기본
        preset_ids = list(presets)
        for i in range(count):
            pid = prompts.select(f"preset_{i}", f"참가자 {i+1} 프리셋", preset_ids, default=preset_ids[0])
            prof = _materialize({"profile_id": pid, "preset": pid, "base_app": False}, presets)
            if mode == "custom":
                for f in _PERSONA_FIELDS:
                    prof[f] = prompts.text(f"{pid}_{f}", f"{pid}.{f}", default=str(prof[f]))
                prof["profile_id"] = prompts.text(f"{pid}_profile_id", f"{pid} 프로필 id", default=pid)
            profiles.append(prof)
        ctx.data["profiles"] = _ensure_unique_ids(profiles)
