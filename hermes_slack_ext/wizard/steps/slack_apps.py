from __future__ import annotations

from pathlib import Path

from hermes_slack_ext.core import manifest, secrets, slack_api
from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts


class SlackAppsStep(Step):
    id = "slack_apps"
    title = "Create Slack apps and tokens"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    # prompt and apply are intertwined via token input, so they are combined into one method and called from prompt.
    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        self.apply_with_prompts(ctx, prompts)

    def apply_with_prompts(self, ctx: WizardContext, prompts: Prompts) -> None:
        participants = [p for p in ctx.data["profiles"] if not p.get("base_app")]

        # C2: --dry-run must not actually create Slack apps, prompt for tokens, or write files.
        # (The side effects live inside prompt(), so the engine's apply skip alone won't stop them — guard directly.)
        if ctx.dry_run:
            names = ", ".join(p["profile_id"] for p in participants)
            print(f"[dry-run] skipping creation/tokens/wiring of {len(participants)} participant app(s): {names}")
            return

        self._rotate_config_token(ctx)  # I3: best-effort rotation to handle the 12h expiry
        config_token = ctx.data["config_token"]
        env_dir = Path(ctx.data.get("profile_env_dir")
                       or (Path.home() / ".hermes" / "hermes-slack-ext" / "envs"))
        channel = ctx.data.get("channel_id", "")
        created_ids = ctx.data.setdefault("created_app_ids", [])
        # Pre-created app ids (profile_id→app_id). When present, skip create_app to avoid
        # duplicate creation (reinstall / pre-provisioning scenarios and headless reproducibility).
        pre_ids = ctx.data.get("participant_app_ids", {}) or {}

        for prof in participants:
            if prof.get("app_id"):
                continue  # I2: do not recreate an already-created profile (idempotent re-run)
            pid = prof["profile_id"]
            if pre_ids.get(pid):
                prof["app_id"] = pre_ids[pid]  # reuse pre-created app — skip create
            else:
                man = manifest.participant_manifest(prof["slack_app_display_name"])
                resp = slack_api.create_app(config_token, man)
                app_id = resp.get("app_id", "")
                if app_id:
                    created_ids.append(app_id)
                prof["app_id"] = app_id
                # Show where to install the created app (so the interactive user can find where to get the tokens).
                oauth_url = resp.get("oauth_authorize_url", "")
                print(f"\n[{pid}] app created (app_id={app_id}) — install it, then paste the 2 tokens:")
                print(f"  Install: https://api.slack.com/apps/{app_id} → Install App → Install to Workspace")
                if oauth_url:
                    print(f"  (or OAuth link: {oauth_url})")
                print("  App-Level Token: Basic Information → App-Level Tokens → create with connections:write\n")
            bot = prompts.password(f"{pid}_bot_token", f"[{pid}] Bot Token after install (xoxb-...)")
            app_tok = prompts.password(f"{pid}_app_token", f"[{pid}] App-Level Token (xapp-...)")
            env_path = env_dir / f"{pid}.env"
            secrets.write_env(env_path, {"SLACK_BOT_TOKEN": bot, "SLACK_APP_TOKEN": app_tok})
            prof["env_path"] = str(env_path)

            # Automatic: get bot_user_id via auth.test. A failure (e.g. a token typo) does not stop the whole loop.
            try:
                info = slack_api.auth_test(bot)
                prof["bot_user_id"] = info.get("user_id", "")
            except slack_api.SlackAPIError:
                prof["bot_user_id"] = ""
                print(f"[{pid}] auth.test failed — check the bot token and re-run this profile.")
            # If it is a public channel, join it (ignore private / already-a-member, etc.). Only attempt when bot_user_id is confirmed.
            if channel and prof.get("bot_user_id"):
                try:
                    slack_api.conversations_join(bot, channel)
                except slack_api.SlackAPIError:
                    pass

    def _rotate_config_token(self, ctx: WizardContext) -> None:
        """The config token expires in 12 hours. If a refresh token is available, rotate it
        and replace the token with the new one. The rotation result is stored in ctx.data and
        is also used by the later moderator_app update. On failure, proceed with the existing
        token (best-effort)."""
        refresh = ctx.data.get("config_refresh_token")
        if not refresh:
            return
        try:
            resp = slack_api.rotate_tokens(refresh)
        except slack_api.SlackAPIError:
            return  # keep the existing token if rotation fails
        if resp.get("token"):
            ctx.data["config_token"] = resp["token"]
        if resp.get("refresh_token"):
            ctx.data["config_refresh_token"] = resp["refresh_token"]
