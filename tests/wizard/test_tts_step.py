from pathlib import Path

import yaml

from hermes_slack_ext.core import tts as T
from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps.tts import TtsStep


def _ctx(tmp_path):
    root = tmp_path / "hermes"
    root.mkdir()
    profs = [
        {"profile_id": "researcher", "persona_display_name": "Researcher", "env_path": str(tmp_path / "r.env")},
        {"profile_id": "backend", "persona_display_name": "Backend", "env_path": str(tmp_path / "b.env")},
    ]
    for p in profs:
        Path(p["env_path"]).write_text("SLACK_BOT_TOKEN=x\n")
    ctx = WizardContext(hermes_root=root)
    ctx.data.update({"features": ["meeting"], "profiles": profs, "staging_dir": str(tmp_path / "staging")})
    return ctx, profs


def test_tts_skipped_is_text_only(tmp_path):
    ctx, _ = _ctx(tmp_path)
    step = TtsStep()
    step.prompt(ctx, ScriptedPrompts({"tts_enable": False}))
    step.apply(ctx)
    assert ctx.data["tts"] == {"enabled": False}
    staged = list((tmp_path / "staging").glob("*.tts.yaml")) if (tmp_path / "staging").exists() else []
    assert staged == []


def test_tts_edge_cycles_voices_round_robin(tmp_path):
    # Fixed-catalog providers auto-assign voices by cycling in profile order — no
    # per-profile prompt — and wrap around when there are more profiles than
    # voices (edge-tts ko-KR has only 3, so larger meetings reuse voices by design).
    cat = T.load_voice_catalog()
    vals = [v["value"] for v in cat["edge"]["voices"]]
    n = len(vals) + 2  # force a wraparound past the end of the list
    root = tmp_path / "hermes"; root.mkdir()
    profs = []
    for i in range(n):
        ep = tmp_path / f"p{i}.env"; ep.write_text("SLACK_BOT_TOKEN=x\n")
        profs.append({"profile_id": f"p{i}", "persona_display_name": f"P{i}", "env_path": str(ep)})
    ctx = WizardContext(hermes_root=root)
    ctx.data.update({"features": ["meeting"], "profiles": profs, "staging_dir": str(tmp_path / "staging")})
    step = TtsStep()
    # only tts_enable + tts_provider scripted — voices are auto-cycled, not prompted
    step.prompt(ctx, ScriptedPrompts({"tts_enable": True, "tts_provider": "edge"}))
    step.apply(ctx)
    for i, p in enumerate(profs):
        block = yaml.safe_load((tmp_path / "staging" / f"{p['profile_id']}.tts.yaml").read_text())
        assert block["tts"]["provider"] == "edge"
        assert block["voice"]["auto_tts"] is False
        assert block["tts"]["edge"]["voice"] == vals[i % len(vals)], f"profile {i} voice off-cycle"
    # explicit wraparound: the profile just past the list end reuses the first voice
    assert ctx.data["tts"]["voices"][f"p{len(vals)}"] == vals[0]


def test_tts_elevenlabs_writes_key_and_voice_id(tmp_path):
    ctx, profs = _ctx(tmp_path)
    step = TtsStep()
    step.prompt(ctx, ScriptedPrompts({
        "tts_enable": True, "tts_provider": "elevenlabs", "tts_elevenlabs_key": "EL_SECRET",
        "tts_voice_researcher": "voiceR", "tts_voice_backend": "voiceB",   # account-specific -> text voice ids
    }))
    step.apply(ctx)
    env = Path(profs[0]["env_path"]).read_text()
    assert "ELEVENLABS_API_KEY=EL_SECRET" in env
    block = yaml.safe_load((tmp_path / "staging" / "researcher.tts.yaml").read_text())
    assert block["tts"]["provider"] == "elevenlabs"
    assert block["tts"]["elevenlabs"]["voice_id"] == "voiceR"
