from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hermes_slack_ext.core import backups, hermes, patcher
from hermes_slack_ext.wizard.engine import Step, WizardContext

_OVERLAY = Path(__file__).resolve().parents[2] / "overlays"


class BoardStep(Step):
    id = "board"
    title = "보드 설치"

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
        # slack.py는 *패치 전(클린)* 상태일 때만 백업한다. 이미 패치된 파일을 백업하면
        # uninstall이 패치 버전을 "복원"해 원복이 무력화된다(클린 백업 보존이 불변식).
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

    def verify(self, ctx: WizardContext) -> None:
        root = Path(ctx.hermes_root)
        py = hermes.venv_python(root)
        subprocess.run([str(py), "-m", "py_compile",
                        "gateway/platforms/slack.py",
                        "gateway/platforms/slack_kanban_board.py"],
                       cwd=str(root), check=True)
