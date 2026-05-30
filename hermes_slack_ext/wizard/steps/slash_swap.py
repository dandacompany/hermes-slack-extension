from __future__ import annotations

import json
from pathlib import Path

from hermes_slack_ext.core import manifest
from hermes_slack_ext.wizard.engine import Step, WizardContext


class SlashSwapStep(Step):
    id = "slash_swap"
    title = "슬래시 스왑"

    def should_run(self, ctx: WizardContext) -> bool:
        return bool(set(ctx.data.get("features", [])) & {"board", "meeting"})

    def apply(self, ctx: WizardContext) -> None:
        features = ctx.data.get("features", [])
        name = ctx.data.get("moderator_name", "Hermes")
        full = manifest.fetch_full_manifest(ctx.hermes_root, name, "Your Hermes agent on Slack")
        drop, add = manifest.entries_for_features(features)
        swapped = manifest.swap_slashes(full, drop=drop, add=add)

        out = Path(ctx.data.get("manifest_out")
                   or (Path.home() / ".hermes/hermes-slack-ext/base-manifest.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(swapped, indent=2, ensure_ascii=False), encoding="utf-8")
        ctx.data["base_manifest_path"] = str(out)
        ctx.data["slash_dropped"] = drop
