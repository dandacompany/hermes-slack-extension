from __future__ import annotations

from typing import Any, Sequence


class PromptExhausted(RuntimeError):
    """Raised when a scripted answer key is missing or its queue is empty."""


class Prompts:
    """Interactive prompts backed by questionary. Each method takes a stable
    ``key`` (used by ScriptedPrompts/answers-file) plus the UI args."""

    def select(self, key: str, message: str, choices: Sequence[str], default: str | None = None) -> str:
        import questionary
        return questionary.select(message, choices=list(choices), default=default).unsafe_ask()

    def checkbox(self, key: str, message: str, choices: Sequence[str], default: Sequence[str] = ()) -> list[str]:
        import questionary
        opts = [questionary.Choice(c, checked=c in default) for c in choices]
        return questionary.checkbox(message, choices=opts).unsafe_ask()

    def text(self, key: str, message: str, default: str = "") -> str:
        import questionary
        return questionary.text(message, default=default).unsafe_ask()

    def confirm(self, key: str, message: str, default: bool = True) -> bool:
        import questionary
        return questionary.confirm(message, default=default).unsafe_ask()

    def password(self, key: str, message: str) -> str:
        import questionary
        return questionary.password(message).unsafe_ask()


class ScriptedPrompts(Prompts):
    """Non-interactive prompts: answers come from a dict of key -> queue.

    Used by tests and by ``--answers-file`` headless runs. A list value is a
    FIFO queue; a non-list value is returned once."""

    def __init__(self, answers: dict[str, Any]):
        self._queues: dict[str, list[Any]] = {
            k: list(v) if isinstance(v, list) else [v] for k, v in answers.items()
        }

    def _next(self, key: str) -> Any:
        q = self._queues.get(key)
        if not q:
            raise PromptExhausted(f"no scripted answer for key={key!r}")
        return q.pop(0)

    def select(self, key, message, choices, default=None):
        return self._next(key)

    def checkbox(self, key, message, choices, default=()):
        return self._next(key)

    def text(self, key, message, default=""):
        return self._next(key)

    def confirm(self, key, message, default=True):
        return self._next(key)

    def password(self, key, message):
        return self._next(key)
