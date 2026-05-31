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
        participants = [p for p in ctx.data["profiles"] if not p.get("base_app")]

        # C2: --dry-run은 실제 Slack 앱 생성·토큰 입력·파일 기록을 하지 않는다.
        # (side effect가 prompt() 안에 있어 엔진의 apply 스킵만으로는 막히지 않으므로 직접 가드)
        if ctx.dry_run:
            names = ", ".join(p["profile_id"] for p in participants)
            print(f"[dry-run] 참가자 앱 {len(participants)}개 생성·토큰·배선 건너뜀: {names}")
            return

        self._rotate_config_token(ctx)  # I3: 12h 만료 대비 best-effort 회전
        config_token = ctx.data["config_token"]
        env_dir = Path(ctx.data.get("profile_env_dir")
                       or (Path.home() / ".hermes" / "hermes-slack-ext" / "envs"))
        channel = ctx.data.get("channel_id", "")
        created_ids = ctx.data.setdefault("created_app_ids", [])
        # 사전 생성된 앱 id(profile_id→app_id). 있으면 create_app을 건너뛰어 중복 생성을
        # 막는다(재설치/사전 프로비저닝 시나리오·헤드리스 재현성).
        pre_ids = ctx.data.get("participant_app_ids", {}) or {}

        for prof in participants:
            if prof.get("app_id"):
                continue  # I2: 이미 생성된 프로필은 재생성하지 않는다(재실행 멱등)
            pid = prof["profile_id"]
            if pre_ids.get(pid):
                prof["app_id"] = pre_ids[pid]  # 사전 생성 앱 재사용 — create 생략
            else:
                man = manifest.participant_manifest(prof["slack_app_display_name"])
                resp = slack_api.create_app(config_token, man)
                app_id = resp.get("app_id", "")
                if app_id:
                    created_ids.append(app_id)
                prof["app_id"] = app_id
                # 생성된 앱의 설치 위치를 안내한다(대화형 사용자가 토큰 발급처를 찾도록).
                oauth_url = resp.get("oauth_authorize_url", "")
                print(f"\n[{pid}] 앱 생성됨 (app_id={app_id}) — 설치 후 토큰 2개를 붙여넣으세요:")
                print(f"  설치: https://api.slack.com/apps/{app_id} → Install App → Install to Workspace")
                if oauth_url:
                    print(f"  (또는 OAuth 링크: {oauth_url})")
                print("  App-Level Token: Basic Information → App-Level Tokens → connections:write 로 생성\n")
            bot = prompts.password(f"{pid}_bot_token", f"[{pid}] Install 후 Bot Token (xoxb-...)")
            app_tok = prompts.password(f"{pid}_app_token", f"[{pid}] App-Level Token (xapp-...)")
            env_path = env_dir / f"{pid}.env"
            secrets.write_env(env_path, {"SLACK_BOT_TOKEN": bot, "SLACK_APP_TOKEN": app_tok})
            prof["env_path"] = str(env_path)

            # 자동: auth.test로 bot_user_id. 토큰 오타 등으로 실패해도 전체 루프를 멈추지 않는다.
            try:
                info = slack_api.auth_test(bot)
                prof["bot_user_id"] = info.get("user_id", "")
            except slack_api.SlackAPIError:
                prof["bot_user_id"] = ""
                print(f"[{pid}] auth.test 실패 — 봇 토큰을 확인하고 이 프로필을 다시 실행하세요.")
            # 공개 채널이면 join(비공개/이미 멤버 등은 무시). bot_user_id 확인된 경우에만 시도.
            if channel and prof.get("bot_user_id"):
                try:
                    slack_api.conversations_join(bot, channel)
                except slack_api.SlackAPIError:
                    pass

    def _rotate_config_token(self, ctx: WizardContext) -> None:
        """config 토큰은 12시간 만료. refresh 토큰이 있으면 회전해 새 토큰으로 교체한다.
        회전 결과는 ctx.data에 저장되어 이후 moderator_app의 update에도 쓰인다.
        실패해도 기존 토큰으로 진행한다(best-effort)."""
        refresh = ctx.data.get("config_refresh_token")
        if not refresh:
            return
        try:
            resp = slack_api.rotate_tokens(refresh)
        except slack_api.SlackAPIError:
            return  # 회전 실패 시 기존 토큰 유지
        if resp.get("token"):
            ctx.data["config_token"] = resp["token"]
        if resp.get("refresh_token"):
            ctx.data["config_refresh_token"] = resp["refresh_token"]
