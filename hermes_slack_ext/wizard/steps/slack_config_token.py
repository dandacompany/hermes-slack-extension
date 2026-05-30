from __future__ import annotations

from hermes_slack_ext.core import secrets
from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts


class SlackConfigTokenStep(Step):
    id = "slack_config_token"
    title = "Slack App Configuration Token"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        # api.slack.com/apps → "Your App Configuration Tokens"에서 발급. password로 받아 미출력.
        token = prompts.password("config_token", "App Configuration Token (xoxe-...)")
        refresh = prompts.password("refresh_token", "Configuration Refresh Token (xoxe-1-...)")
        ctx.data["config_token"] = token
        ctx.data["config_refresh_token"] = refresh
        self._collect_context(ctx, prompts)

    def _collect_context(self, ctx: WizardContext, prompts: Prompts) -> None:
        """회의 컨텍스트(비밀 아닌 공개 id)를 수집한다. 헤드리스(non_interactive)는
        --answers-file 주입에 의존하므로 프롬프트를 건너뛰고, 대화형에서만 누락된 값을
        묻는다. moderator_bot_user_id는 베이스 Hermes 앱(모더레이터)의 Bot User ID로,
        allowed_users에 포함되어야 모더레이터→참가자 멘션 라우팅이 동작한다."""
        if ctx.non_interactive:
            return
        if not ctx.data.get("channel_id"):
            ctx.data["channel_id"] = prompts.text(
                "channel_id", "회의 채널 ID (Cxxxxxxxx)", default="")
        if not ctx.data.get("human_user_id"):
            ctx.data["human_user_id"] = prompts.text(
                "human_user_id", "당신의 Slack User ID (Uxxxxxxxx)", default="")
        if not ctx.data.get("moderator_bot_user_id"):
            ctx.data["moderator_bot_user_id"] = prompts.text(
                "moderator_bot_user_id",
                "모더레이터(베이스 Hermes 앱) Bot User ID (Uxxxxxxxx)", default="")

    def apply(self, ctx: WizardContext) -> None:
        # 마스킹된 확인만 출력(값 노출 금지). 실제 유효성은 slack_apps 단계의 첫 호출에서 확인.
        masked = secrets.mask(ctx.data.get("config_token", ""))
        print(f"[config token] 등록됨: {masked}")
