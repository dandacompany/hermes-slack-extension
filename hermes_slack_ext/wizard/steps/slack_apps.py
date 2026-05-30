from __future__ import annotations

from pathlib import Path

from hermes_slack_ext.core import manifest, secrets, slack_api
from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts


class SlackAppsStep(Step):
    id = "slack_apps"
    title = "Slack 앱 생성·토큰"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    # prompt와 apply가 토큰 입력으로 얽히므로, 한 메서드로 묶고 prompt에서 호출한다.
    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        self.apply_with_prompts(ctx, prompts)

    def apply_with_prompts(self, ctx: WizardContext, prompts: Prompts) -> None:
        config_token = ctx.data["config_token"]
        env_dir = Path(ctx.data.get("profile_env_dir")
                       or (Path.home() / ".hermes" / "hermes-slack-ext" / "envs"))
        channel = ctx.data.get("channel_id", "")
        created_ids = ctx.data.setdefault("created_app_ids", [])

        for prof in ctx.data["profiles"]:
            if prof.get("base_app"):
                continue  # 모더레이터(기존 베이스 앱)는 moderator_app 스텝에서 처리
            pid = prof["profile_id"]
            man = manifest.participant_manifest(prof["slack_app_display_name"])
            resp = slack_api.create_app(config_token, man)
            app_id = resp.get("app_id", "")
            if app_id:
                created_ids.append(app_id)
            prof["app_id"] = app_id

            # 사용자 수동: 설치(OAuth) + app-level 토큰 발급 후 두 토큰 붙여넣기(미출력)
            bot = prompts.password(f"{pid}_bot_token", f"[{pid}] Install 후 Bot Token (xoxb-...)")
            app_tok = prompts.password(f"{pid}_app_token", f"[{pid}] App-Level Token (xapp-...)")
            env_path = env_dir / f"{pid}.env"
            secrets.write_env(env_path, {"SLACK_BOT_TOKEN": bot, "SLACK_APP_TOKEN": app_tok})
            prof["env_path"] = str(env_path)

            # 자동: auth.test로 bot_user_id, 공개채널이면 join
            info = slack_api.auth_test(bot)
            prof["bot_user_id"] = info.get("user_id", "")
            if channel:
                try:
                    slack_api.conversations_join(bot, channel)
                except slack_api.SlackAPIError:
                    pass  # 비공개/이미 멤버 등은 무시(가이드로 처리)
