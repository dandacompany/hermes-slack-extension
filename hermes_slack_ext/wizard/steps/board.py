from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hermes_slack_ext.core import backups, hermes, patcher
from hermes_slack_ext.wizard.engine import Step, WizardContext

_OVERLAY = Path(__file__).resolve().parents[2] / "overlays"
_BOARD_SKILL = Path(__file__).resolve().parents[2] / "board" / "hermes-board" / "SKILL.md"


class BoardStep(Step):
    id = "board"
    title = "Install board"

    def should_run(self, ctx: WizardContext) -> bool:
        return "board" in ctx.data.get("features", [])

    def apply(self, ctx: WizardContext) -> None:
        root = Path(ctx.hermes_root)
        slack_py = hermes.slack_py_path(root)
        backup_root = Path(ctx.data["backup_root"])

        text = slack_py.read_text()
        rels = [
            "gateway/platforms/slack_kanban_board.py",
            "tests/test_slack_kanban_board.py",
        ]
        # Back up slack.py only when it is in the *pre-patch (clean)* state. Backing up an
        # already-patched file would let uninstall "restore" the patched version, defeating
        # the rollback (preserving the clean backup is an invariant).
        if not (patcher.board_markers_present(text) or patcher.meeting_markers_present(text)):
            rels.insert(0, "gateway/platforms/slack.py")
        backups.backup_files(root, rels, backup_root)

        frag = (_OVERLAY / "gateway/platforms/slack_board_methods.pyfrag").read_text()
        patched = patcher.apply_board_patch(text, frag)
        slack_py.write_text(patched)

        shutil.copy2(_OVERLAY / "gateway/platforms/slack_kanban_board.py",
                     root / "gateway/platforms/slack_kanban_board.py")
        ovl_test = _OVERLAY / "tests/test_slack_kanban_board.py"
        if ovl_test.exists():
            (root / "tests").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ovl_test, root / "tests/test_slack_kanban_board.py")

        # Enable the `kanban` toolset so the agent can manage the board in natural
        # language (kanban_create/move/...). The Block Kit UI alone only gives the
        # Add button; without this toolset the agent has no kanban tools and falls
        # back to a `hermes`/`sqlite3` CLI that may not be on PATH, so NL requests
        # silently create nothing. Hermes config.yaml lives in HERMES_HOME (data
        # root), not the code root being patched.
        cfg = hermes.config_path()
        outcome = hermes.enable_toolset(cfg, "kanban")
        if outcome == "enabled":
            print(f"[board] enabled the `kanban` toolset in {cfg} — restart the gateway to load it.")
        elif outcome == "no-config":
            print(f"[board] could not find {cfg}; add `kanban` to your config.yaml `toolsets:` "
                  "to enable natural-language board management (the Add button works without it).")

        # Install the board-management skill so the agent drives the board
        # predictably (respect the requested column, treat triage as the
        # decomposition lane) instead of reshuffling/auto-assigning or shelling out.
        skills_dir = Path(ctx.data.get("skills_dir")
                          or (hermes.hermes_home() / "skills"))
        dest = skills_dir / "hermes-board"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_BOARD_SKILL, dest / "SKILL.md")

    def verify(self, ctx: WizardContext) -> None:
        root = Path(ctx.hermes_root)
        py = hermes.venv_python(root)
        subprocess.run([str(py), "-m", "py_compile",
                        "gateway/platforms/slack.py",
                        "gateway/platforms/slack_kanban_board.py"],
                       cwd=str(root), check=True)
