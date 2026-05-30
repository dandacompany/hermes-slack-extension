from __future__ import annotations

import sys
from pathlib import Path

SUPPORTED_VERSIONS = ("0.12.0", "0.13.0", "0.14.0", "0.15.0", "0.15.1")
DEFAULT_ROOT = Path.home() / ".hermes" / "hermes-agent"


def detect_version(hermes_root: Path) -> str | None:
    pyproject = Path(hermes_root) / "pyproject.toml"
    if not pyproject.exists():
        return None
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("version") and "=" in s:
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def is_supported(version: str | None) -> bool:
    return version in SUPPORTED_VERSIONS


def venv_python(hermes_root: Path) -> Path:
    candidate = Path(hermes_root) / "venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def slack_py_path(hermes_root: Path) -> Path:
    return Path(hermes_root) / "gateway" / "platforms" / "slack.py"
