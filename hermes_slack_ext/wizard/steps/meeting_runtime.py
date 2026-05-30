from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from hermes_slack_ext.core import backups, hermes, patcher
from hermes_slack_ext.wizard.engine import Step, WizardContext

_OVERLAY = Path(__file__).resolve().parents[2] / "overlays"


class MeetingRuntimeStep(Step):
    id = "meeting_runtime"
    title = "미팅 Block Kit 런타임 패치"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    def apply(self, ctx: WizardContext) -> None:
        root = ctx.hermes_root
        backup_root = Path(ctx.data.get("backup_root")
                           or (root.parent / "backups" / "hermes-slack-ext"))
        slack_py = root / "gateway/platforms/slack.py"
        text = slack_py.read_text(encoding="utf-8")
        rels = ["gateway/platforms/slack_meeting_room.py",
                "tests/test_slack_meeting_room.py"]
        # slack.py는 *패치 전(클린)* 상태일 때만 백업한다(클린 백업 보존 불변식 — 보드 스텝과 동일).
        if not (patcher.board_markers_present(text) or patcher.meeting_markers_present(text)):
            rels.insert(0, "gateway/platforms/slack.py")
        backups.backup_files(root, rels, backup_root)

        # 1) slack.py 미팅 패치 (보드와 합성·멱등)
        frag = (_OVERLAY / "gateway/platforms/slack_meeting_methods.pyfrag").read_text(encoding="utf-8")
        slack_py.write_text(patcher.apply_meeting_patch(text, frag), encoding="utf-8")

        # 2) 오버레이 모듈 복사
        shutil.copy2(_OVERLAY / "gateway/platforms/slack_meeting_room.py",
                     root / "gateway/platforms/slack_meeting_room.py")
        test_src = _OVERLAY / "tests/test_slack_meeting_room.py"
        if test_src.exists():
            (root / "tests").mkdir(parents=True, exist_ok=True)
            shutil.copy2(test_src, root / "tests/test_slack_meeting_room.py")

        # 3) 참가자 사이드카 기록(모더레이터=base_app 제외) — 모달 multi-select 옵션 소스
        names = [p.get("persona_display_name", p.get("profile_id", ""))
                 for p in ctx.data.get("profiles", []) if not p.get("base_app")]
        home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
        sidecar = home / "hermes-slack-ext" / "meeting_participants.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")

    def verify(self, ctx: WizardContext) -> None:
        root = ctx.hermes_root
        py = hermes.venv_python(root)
        subprocess.run(
            [str(py), "-m", "py_compile",
             "gateway/platforms/slack.py", "gateway/platforms/slack_meeting_room.py"],
            cwd=str(root), check=True, capture_output=True,
        )
