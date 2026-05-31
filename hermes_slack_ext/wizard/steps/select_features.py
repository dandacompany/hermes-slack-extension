from __future__ import annotations

from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts

ALL_FEATURES = ["board", "meeting", "tts"]


class SelectFeaturesStep(Step):
    id = "select_features"
    title = "Select features"

    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        chosen = prompts.checkbox(
            "features", "Select the features to install", ALL_FEATURES, default=["board", "meeting"]
        )
        ctx.data["features"] = list(chosen)
