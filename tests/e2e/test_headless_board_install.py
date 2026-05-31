import os
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from hermes_slack_ext.cli import app

REAL = Path(os.environ.get("HERMES_ROOT", str(Path.home() / ".hermes/hermes-agent")))
REAL_VENV_PY = REAL / "venv/bin/python"


@pytest.mark.skipif(
    not (REAL / "gateway/platforms/slack.py").exists() or not REAL_VENV_PY.exists(),
    reason="no real Hermes checkout/venv",
)
def test_headless_board_install(tmp_path):
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "tests").mkdir()
    shutil.copy(REAL / "gateway/platforms/slack.py", root / "gateway/platforms/slack.py")
    shutil.copy(REAL / "pyproject.toml", root / "pyproject.toml")
    # Link the entire real Hermes venv into the temporary clone so slash_swap can generate the manifest.
    # Symlinking only venv/bin/python loses pyvenv.cfg and fails to find hermes_cli, so
    # symlink the whole venv directory to preserve the venv context (site-packages).
    (root / "venv").symlink_to((REAL / "venv").resolve())

    answers = {
        "features": ["board"],
        "manifest_out": str(tmp_path / "base-manifest.json"),
    }
    af = tmp_path / "answers.yaml"
    af.write_text(yaml.safe_dump(answers))

    result = CliRunner().invoke(app, [
        "install", "--hermes-root", str(root),
        "--answers-file", str(af), "--non-interactive",
        "--state-dir", str(tmp_path / "state"),
    ])
    assert result.exit_code == 0, result.stdout
    patched = (root / "gateway/platforms/slack.py").read_text()
    assert '@self._app.command("/board")' in patched
    assert Path(answers["manifest_out"]).exists()
