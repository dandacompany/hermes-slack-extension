from __future__ import annotations

import json
from pathlib import Path

from hermes_slack_ext.core import slack_api
from hermes_slack_ext.wizard.engine import Step, WizardContext


class ModeratorAppStep(Step):
    id = "moderator_app"
    title = "Apply moderator (base) app manifest"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", []) and bool(ctx.data.get("base_manifest_path"))

    def apply(self, ctx: WizardContext) -> None:
        man_path = Path(ctx.data["base_manifest_path"])
        base_app_id = ctx.data.get("base_app_id")
        if base_app_id and ctx.data.get("config_token"):
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
            slack_api.update_app(ctx.data["config_token"], base_app_id, manifest)
            print(f"[moderator] base app manifest updated: {base_app_id}")
        else:
            print(f"[moderator] base_app_id not set — apply manually: paste {man_path} "
                  f"into App Manifest and click Save.")
