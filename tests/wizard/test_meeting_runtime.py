import json
from pathlib import Path

from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.steps import meeting_runtime as MR


_SKELETON = '''\
class SlackAdapter:
    def __init__(self):
        self._slash_command_contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}

    async def connect(self):
            import re as _re

            _slash_names = [name for name, _d, _h in slack_native_slashes()]
            # Start Socket Mode handler in background
            self._handler = None

    async def _handle_slash_confirm_action(self, ack, body, action):
        await ack()
'''


def _root(tmp_path):
    root = tmp_path / "hermes-agent"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "gateway/platforms/slack.py").write_text(_SKELETON)
    return root


def test_skips_when_no_meeting(tmp_path):
    ctx = WizardContext(hermes_root=_root(tmp_path))
    ctx.data["features"] = ["board"]
    assert MR.MeetingRuntimeStep().should_run(ctx) is False


def test_patches_copies_overlay_and_writes_sidecar(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    ctx = WizardContext(hermes_root=root)
    ctx.data.update({
        "features": ["meeting"],
        "backup_root": str(tmp_path / "bk"),
        "profiles": [
            {"profile_id": "moderator", "base_app": True, "persona_display_name": "Moderator"},
            {"profile_id": "researcher", "base_app": False, "persona_display_name": "Researcher"},
            {"profile_id": "designer", "base_app": False, "persona_display_name": "Designer"},
        ],
    })
    step = MR.MeetingRuntimeStep()
    step.apply(ctx)

    patched = (root / "gateway/platforms/slack.py").read_text()
    assert '@self._app.command("/meeting")' in patched
    assert (root / "gateway/platforms/slack_meeting_room.py").exists()
    sidecar = Path(tmp_path / "home" / "hermes-slack-ext" / "meeting_participants.json")
    names = json.loads(sidecar.read_text())
    assert names == ["Researcher", "Designer"]   # base_app(모더레이터) 제외
