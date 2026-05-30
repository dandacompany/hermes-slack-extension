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
    reason="실 Hermes 체크아웃/venv 없음",
)
def test_headless_board_install(tmp_path):
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "tests").mkdir()
    shutil.copy(REAL / "gateway/platforms/slack.py", root / "gateway/platforms/slack.py")
    shutil.copy(REAL / "pyproject.toml", root / "pyproject.toml")
    # slash_swap의 manifest 생성을 위해 실 Hermes venv 전체를 임시 클론에 연결.
    # venv/bin/python 단독 심링크는 pyvenv.cfg를 잃어 hermes_cli를 못 찾으므로,
    # venv 디렉터리 전체를 심링크해 venv 컨텍스트(site-packages)를 유지한다.
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
