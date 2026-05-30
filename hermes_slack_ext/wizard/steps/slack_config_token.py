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

    def apply(self, ctx: WizardContext) -> None:
        # 마스킹된 확인만 출력(값 노출 금지). 실제 유효성은 slack_apps 단계의 첫 호출에서 확인.
        masked = secrets.mask(ctx.data.get("config_token", ""))
        print(f"[config token] 등록됨: {masked}")
