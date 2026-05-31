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
        # Generated at api.slack.com/apps → "Your App Configuration Tokens". Read as a password so it is not echoed.
        token = prompts.password("config_token", "App Configuration Token (xoxe-...)")
        refresh = prompts.password("refresh_token", "Configuration Refresh Token (xoxe-1-...)")
        ctx.data["config_token"] = token
        ctx.data["config_refresh_token"] = refresh
        self._collect_context(ctx, prompts)

    def _collect_context(self, ctx: WizardContext, prompts: Prompts) -> None:
        """Collect meeting context (non-secret, public ids). Headless mode
        (non_interactive) relies on --answers-file injection, so prompts are
        skipped; only the interactive flow asks for missing values.
        moderator_bot_user_id is the Bot User ID of the base Hermes app (the
        moderator); it must be included in allowed_users for moderator→participant
        mention routing to work."""
        if ctx.non_interactive:
            return
        if not ctx.data.get("channel_id"):
            ctx.data["channel_id"] = prompts.text(
                "channel_id", "Meeting channel ID (Cxxxxxxxx)", default="")
        if not ctx.data.get("human_user_id"):
            ctx.data["human_user_id"] = prompts.text(
                "human_user_id", "Your Slack User ID (Uxxxxxxxx)", default="")
        if not ctx.data.get("moderator_bot_user_id"):
            ctx.data["moderator_bot_user_id"] = prompts.text(
                "moderator_bot_user_id",
                "Moderator (base Hermes app) Bot User ID (Uxxxxxxxx)", default="")

    def apply(self, ctx: WizardContext) -> None:
        # Print only a masked confirmation (never expose the value). Actual validity is checked on the first call in the slack_apps step.
        masked = secrets.mask(ctx.data.get("config_token", ""))
        print(f"[config token] registered: {masked}")
