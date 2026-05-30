from __future__ import annotations

import shutil
from pathlib import Path

from hermes_slack_ext.core import profiles as P
from hermes_slack_ext.core import secrets
from hermes_slack_ext.wizard.engine import Step, WizardContext

_MODERATOR_SKILL = Path(__file__).resolve().parents[2] / "meeting" / "hermes-meeting" / "SKILL.md"


class WireupStep(Step):
    id = "wireup"
    title = "회의 배선 (프롬프트·bot-to-bot·moderator 스킬)"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    def apply(self, ctx: WizardContext) -> None:
        profs = ctx.data["profiles"]
        human = ctx.data.get("human_user_id", "")

        moderator = next((p for p in profs if p.get("base_app")), profs[0])
        mod_name = moderator["persona_display_name"]
        # 모더레이터(베이스 Hermes 앱)는 참가자 루프의 auth.test 캡처를 거치지 않아
        # bot_user_id가 비어 있다. ctx의 moderator_bot_user_id로 보충해야
        # allowed_users에 포함되어 모더레이터→참가자 멘션 라우팅이 동작한다.
        mod_bot = ctx.data.get("moderator_bot_user_id", "")
        if mod_bot and not moderator.get("bot_user_id"):
            moderator["bot_user_id"] = mod_bot
        bot_ids = [p["bot_user_id"] for p in profs if p.get("bot_user_id")]
        allowed = P.build_allowed_users(human, bot_ids)

        staging = Path(ctx.data.get("staging_dir")
                       or (Path.home() / ".hermes" / "hermes-slack-ext" / "staging"))
        staging.mkdir(parents=True, exist_ok=True)

        # 1) bot-to-bot env (각 프로필 .env)
        for p in profs:
            env_path = p.get("env_path")
            if env_path:
                secrets.write_env(Path(env_path), {
                    "SLACK_ALLOWED_USERS": allowed,
                    "SLACK_ALLOW_BOTS": "mentions",
                    "SLACK_REQUIRE_MENTION": "true",
                    "SLACK_STRICT_MENTION": "true",
                    "SLACK_INJECT_BOT_MENTION_CONTEXT": "true",
                })

        # 2) 채널 프롬프트 렌더 → 스테이징
        participant_mentions = [f"- {p['persona_display_name']}"
                                for p in profs if not p.get("base_app")]
        (staging / "moderator.channel-prompt.txt").write_text(
            P.render_moderator_prompt(participant_mentions), encoding="utf-8")
        for p in profs:
            if p.get("base_app"):
                continue
            text = P.render_participant_prompt(p, moderator_name=mod_name, role=p.get("role_job", ""))
            (staging / f"{p['profile_id']}.channel-prompt.txt").write_text(text, encoding="utf-8")

        # 3) moderator 스킬 설치
        skills_dir = Path(ctx.data.get("skills_dir") or (Path.home() / ".hermes" / "skills"))
        dest = skills_dir / "hermes-meeting"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_MODERATOR_SKILL, dest / "SKILL.md")

        ctx.data["staging_dir"] = str(staging)
        print(f"[wireup] 채널 프롬프트 스테이징: {staging} (각 프로필 config의 channel_prompts에 반영하세요)")
