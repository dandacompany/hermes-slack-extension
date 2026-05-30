from __future__ import annotations

import json
from pathlib import Path


class WizardState:
    """Resumable wizard state persisted as JSON. Tracks completed step ids and
    a free-form data bag (e.g. detected version, created app_ids)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.completed: list[str] = []
        self.data: dict = {}

    def load(self) -> "WizardState":
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.completed = raw.get("completed", [])
            self.data = raw.get("data", {})
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"completed": self.completed, "data": self.data}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def mark_done(self, step_id: str) -> None:
        if step_id not in self.completed:
            self.completed.append(step_id)

    def is_done(self, step_id: str) -> bool:
        return step_id in self.completed

    def set(self, key: str, value) -> None:
        self.data[key] = value

    def get(self, key: str, default=None):
        return self.data.get(key, default)
