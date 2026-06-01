import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.steps.board import BoardStep

REAL = Path(os.environ.get("HERMES_ROOT", str(Path.home() / ".hermes/hermes-agent")))


@pytest.mark.skipif(not (REAL / "gateway/platforms/slack.py").exists(),
                    reason="no real Hermes checkout")
def test_board_step_patches_and_compiles(tmp_path, monkeypatch):
    # Isolate HERMES_HOME to a temp dir so enabling the kanban toolset never
    # touches the real ~/.hermes/config.yaml.
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("toolsets:\n- hermes-cli\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))

    # copy only the real slack.py into a temporary root
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "tests").mkdir()
    shutil.copy(REAL / "gateway/platforms/slack.py", root / "gateway/platforms/slack.py")
    shutil.copy(REAL / "pyproject.toml", root / "pyproject.toml")

    ctx = WizardContext(hermes_root=root)
    ctx.data["features"] = ["board"]
    ctx.data["backup_root"] = str(tmp_path / "backup")
    BoardStep().apply(ctx)

    patched = (root / "gateway/platforms/slack.py").read_text()
    assert '@self._app.command("/board")' in patched
    assert (root / "gateway/platforms/slack_kanban_board.py").exists()
    # the board step enables the kanban toolset so NL board management works
    import yaml
    assert "kanban" in yaml.safe_load((home / "config.yaml").read_text())["toolsets"]
    # py_compile succeeds
    subprocess.run([sys.executable, "-m", "py_compile",
                    str(root / "gateway/platforms/slack.py")], check=True)
