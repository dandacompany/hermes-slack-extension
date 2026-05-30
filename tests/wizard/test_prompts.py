import pytest

from hermes_slack_ext.wizard.prompts import ScriptedPrompts, PromptExhausted


def test_scripted_returns_queued_values_in_order():
    p = ScriptedPrompts({
        "feature": ["board"],
        "confirm_patch": [True],
    })
    assert p.select("feature", "기능?", ["board", "meeting"]) == "board"
    assert p.confirm("confirm_patch", "패치?") is True


def test_scripted_raises_when_key_missing_or_exhausted():
    p = ScriptedPrompts({"feature": ["board"]})
    p.select("feature", "기능?", ["board"])
    with pytest.raises(PromptExhausted):
        p.select("feature", "기능?", ["board"])
    with pytest.raises(PromptExhausted):
        p.text("unknown", "?")
