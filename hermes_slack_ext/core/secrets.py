from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_env(env_path: Path, kv: dict[str, str]) -> None:
    """Merge kv into a dotenv file (creating it) with mode 0600 from creation.

    Existing keys are overwritten in place; other lines preserved. Never prints
    values. The file is written atomically via a sibling temp file created at
    mode 0600 and replaced into place, so the secret is never exposed through a
    world-readable window (no write-then-chmod race)."""
    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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
    payload = "\n".join(out) + "\n"
    # Atomic write: mkstemp creates the temp file at mode 0600, so the token is
    # restrictive from the first byte. os.replace then swaps it in atomically.
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=str(env_path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, env_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
