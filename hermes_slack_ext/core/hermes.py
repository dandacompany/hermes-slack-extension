from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

SUPPORTED_VERSIONS = ("0.12.0", "0.13.0", "0.14.0", "0.15.0", "0.15.1")  # known-good list (reference)
MIN_SUPPORTED_VERSION = "0.12.0"  # gate: any Hermes >= this is accepted (0.16.0+ included)
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


def _version_tuple(version: str | None) -> tuple[int, int, int] | None:
    """Parse a dotted version into a (major, minor, patch) int tuple.

    Tolerates suffixes (e.g. ``0.16.0.dev1``, ``0.16.0rc2``) by reading the
    leading digits of each of the first three components.
    """
    if not version:
        return None
    nums: list[int] = []
    for token in str(version).strip().split("."):
        digits = ""
        for ch in token:
            if ch.isdigit():
                digits += ch
            else:
                break
        nums.append(int(digits) if digits else 0)
        if len(nums) == 3:
            break
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def is_supported(version: str | None) -> bool:
    """Accept any Hermes version >= ``MIN_SUPPORTED_VERSION`` (0.12.0).

    Previously an exact membership test against ``SUPPORTED_VERSIONS``, which
    rejected newer releases like 0.16.0 even though the extension still works.
    """
    current = _version_tuple(version)
    minimum = _version_tuple(MIN_SUPPORTED_VERSION)
    return current is not None and minimum is not None and current >= minimum


def venv_python(hermes_root: Path) -> Path:
    candidate = Path(hermes_root) / "venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def slack_py_path(hermes_root: Path) -> Path:
    return Path(hermes_root) / "gateway" / "platforms" / "slack.py"


def hermes_home() -> Path:
    """Hermes data dir (config.yaml, sessions, kanban.db). This is HERMES_HOME — the
    *data* root — which is distinct from the *code* root passed around as
    hermes_root. Resolved the same way the wireup/runtime steps do."""
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def config_path(home: Path | None = None) -> Path:
    return (home or hermes_home()) / "config.yaml"


def kanban_toolset_enabled(config: Path | None = None) -> bool:
    """True when the Hermes config enables the ``kanban`` toolset. Natural-language
    board management (kanban_create/move/...) is gated on this — without it the
    agent has no kanban tools and falls back to a CLI that may not be on PATH, so
    only the board's Add button works. Returns False when the config is missing or
    unparseable (treated as not-enabled rather than raising)."""
    cfg_path = config or config_path()
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    return "kanban" in (data.get("toolsets") or [])


def enable_toolset(config: Path, name: str) -> str:
    """Idempotently add ``name`` to the top-level ``toolsets`` list in a Hermes
    config.yaml. Hermes configs are machine-generated (no comments), so a yaml
    round-trip is lossless here. Returns one of: ``"no-config"`` (file missing),
    ``"already"`` (already present), ``"enabled"`` (added)."""
    if not config.exists():
        return "no-config"
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    toolsets = list(data.get("toolsets") or [])
    if name in toolsets:
        return "already"
    toolsets.append(name)
    data["toolsets"] = toolsets
    with config.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, default_flow_style=False,
                       sort_keys=False, width=10 ** 9)
    return "enabled"
