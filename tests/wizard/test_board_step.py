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
                    reason="실 Hermes 체크아웃 없음")
def test_board_step_patches_and_compiles(tmp_path):
    # 실 slack.py만 임시 root로 복제
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
    # py_compile 성공
    subprocess.run([sys.executable, "-m", "py_compile",
                    str(root / "gateway/platforms/slack.py")], check=True)
