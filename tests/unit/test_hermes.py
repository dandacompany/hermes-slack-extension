import shutil
import sys
from pathlib import Path

import pytest

from hermes_slack_ext.core.hermes import detect_version, is_supported, venv_python


def _make_root(tmp_path) -> Path:
    root = tmp_path / "hermes-agent"
    root.mkdir()
    shutil.copy(Path("tests/fixtures/pyproject_0151.toml"), root / "pyproject.toml")
    return root


def test_detect_version(tmp_path):
    root = _make_root(tmp_path)
    assert detect_version(root) == "0.15.1"


def test_detect_version_missing(tmp_path):
    assert detect_version(tmp_path) is None


def test_is_supported():
    assert is_supported("0.15.1") is True
    assert is_supported("0.14.0") is True
    assert is_supported("0.9.0") is False


def test_venv_python_falls_back_to_sys_executable(tmp_path):
    root = _make_root(tmp_path)  # no venv/ dir
    assert venv_python(root) == Path(sys.executable)
