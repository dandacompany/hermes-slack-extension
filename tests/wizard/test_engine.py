from pathlib import Path

from hermes_slack_ext.wizard.engine import Step, WizardContext, Wizard
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.core.state import WizardState


class RecordStep(Step):
    id = "record"
    title = "Record"

    def prompt(self, ctx, prompts):
        ctx.data["chosen"] = prompts.select("pick", "?", ["a", "b"])

    def apply(self, ctx):
        ctx.data["applied"] = True


class SkippedStep(Step):
    id = "skipped"
    title = "Skipped"

    def should_run(self, ctx):
        return False

    def apply(self, ctx):
        ctx.data["should_not_appear"] = True


def test_wizard_runs_steps_and_persists(tmp_path):
    ctx = WizardContext(hermes_root=tmp_path)
    prompts = ScriptedPrompts({"pick": ["b"]})
    state = WizardState(tmp_path / "state.json")
    Wizard([RecordStep(), SkippedStep()], prompts, state).run(ctx)

    assert ctx.data["chosen"] == "b"
    assert ctx.data["applied"] is True
    assert "should_not_appear" not in ctx.data
    assert state.is_done("record")
    assert not state.is_done("skipped")


def test_dry_run_does_not_persist_or_apply(tmp_path):
    ctx = WizardContext(hermes_root=tmp_path, dry_run=True)
    state = WizardState(tmp_path / "state.json")
    Wizard([RecordStep()], ScriptedPrompts({"pick": ["a"]}), state).run(ctx)
    assert "applied" not in ctx.data          # apply skipped
    assert not state.is_done("record")        # not marked done
    assert not (tmp_path / "state.json").exists()  # nothing persisted


def test_completed_steps_are_skipped_on_resume(tmp_path):
    state = WizardState(tmp_path / "state.json")
    state.mark_done("record")
    state.save()
    ctx = WizardContext(hermes_root=tmp_path)
    Wizard([RecordStep()], ScriptedPrompts({}), WizardState(tmp_path / "state.json").load()).run(ctx)
    # record was already done → prompt/apply skipped, so no "applied"
    assert "applied" not in ctx.data
