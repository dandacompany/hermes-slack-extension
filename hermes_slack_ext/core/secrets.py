from __future__ import annotations

import os
from pathlib import Path


def write_env(env_path: Path, kv: dict[str, str]) -> None:
    """Merge kv into a dotenv file (creating it), set mode 0600. Existing keys
    are overwritten in place; other lines preserved. Never prints values."""
    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    keys = set(kv)
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        k = line.split("=", 1)[0].strip() if "=" in line else None
        if k in keys:
            out.append(f"{k}={kv[k]}")
            seen.add(k)
        else:
            out.append(line)
    for k, v in kv.items():
        if k not in seen:
            out.append(f"{k}={v}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)


def mask(token: str) -> str:
    """Return a masked form safe to display. Never reveal more than a short prefix."""
    if not token:
        return "<empty>"
    return token[:8] + "***" if len(token) > 8 else "***"


def verify_keys_present(env_path: Path, keys: list[str]) -> dict[str, bool]:
    """Return {key: present?} without reading or printing values."""
    text = Path(env_path).read_text(encoding="utf-8") if Path(env_path).exists() else ""
    present = {line.split("=", 1)[0].strip() for line in text.splitlines() if "=" in line}
    return {k: k in present for k in keys}
