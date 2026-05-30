from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hermes_slack_ext.wizard.prompts import Prompts
from hermes_slack_ext.core.state import WizardState


@dataclass
class WizardContext:
    """Mutable bag threaded through all steps."""
    hermes_root: Path
    data: dict = field(default_factory=dict)
    non_interactive: bool = False
    dry_run: bool = False


class Step:
    """Base step. Subclasses set ``id``/``title`` and override the hooks.

    Lifecycle per step: should_run → prompt → apply → verify. ``prompt`` reads
    user input via the injected Prompts (interactive or scripted). ``apply``
    performs deterministic side effects. ``verify`` self-checks."""

    id: str = "step"
    title: str = "Step"

    def should_run(self, ctx: WizardContext) -> bool:
        return True

    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        pass

    def apply(self, ctx: WizardContext) -> None:
        pass

    def verify(self, ctx: WizardContext) -> None:
        pass


class Wizard:
    """Drives steps in order, skipping completed/should-not-run steps and
    persisting progress after each applied step."""

    def __init__(self, steps: list[Step], prompts: Prompts, state: WizardState):
        self.steps = steps
        self.prompts = prompts
        self.state = state

    def run(self, ctx: WizardContext) -> WizardContext:
        for step in self.steps:
            if self.state.is_done(step.id):
                continue
            if not step.should_run(ctx):
                continue
            step.prompt(ctx, self.prompts)
            if ctx.dry_run:
                continue
            step.apply(ctx)
            step.verify(ctx)
            self.state.mark_done(step.id)
            self.state.save()
        return ctx
