import shutil
from pathlib import Path

import pytest

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps.detect import DetectStep
from hermes_slack_ext.wizard.steps.select_features import SelectFeaturesStep


def _root(tmp_path):
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    shutil.copy(Path("tests/fixtures/pyproject_0151.toml"), root / "pyproject.toml")
    (root / "gateway/platforms/slack.py").write_text("x\n")
    return root


def test_detect_populates_version(tmp_path):
    ctx = WizardContext(hermes_root=_root(tmp_path))
    step = DetectStep()
    step.apply(ctx)
    assert ctx.data["hermes_version"] == "0.15.1"


def test_detect_rejects_missing_slack_py(tmp_path):
    bad = tmp_path / "empty"
    bad.mkdir()
    ctx = WizardContext(hermes_root=bad)
    with pytest.raises(Exception):
        DetectStep().apply(ctx)


def test_select_features_records_choice(tmp_path):
    ctx = WizardContext(hermes_root=_root(tmp_path))
    DetectStep().apply(ctx)
    SelectFeaturesStep().prompt(ctx, ScriptedPrompts({"features": [["board"]]}))
    assert ctx.data["features"] == ["board"]
