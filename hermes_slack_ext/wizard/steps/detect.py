from __future__ import annotations

from hermes_slack_ext.core import hermes
from hermes_slack_ext.wizard.engine import Step, WizardContext


class DetectStep(Step):
    id = "detect"
    title = "Detect Hermes"

    def apply(self, ctx: WizardContext) -> None:
        root = ctx.hermes_root
        if not hermes.slack_py_path(root).exists():
            raise FileNotFoundError(f"slack.py not found: {hermes.slack_py_path(root)}")
        version = hermes.detect_version(root)
        ctx.data["hermes_version"] = version
        ctx.data["hermes_supported"] = hermes.is_supported(version)
        if not hermes.is_supported(version):
            raise RuntimeError(
                f"Unsupported Hermes version: {version}. "
                f"Requires Hermes >= {hermes.MIN_SUPPORTED_VERSION}."
            )
