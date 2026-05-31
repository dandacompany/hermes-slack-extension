import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from hermes_slack_ext import cli


def test_install_writes_record_without_secrets(tmp_path, monkeypatch):
    from hermes_slack_ext.wizard.engine import Step

    class _Seed(Step):
        id = "seed"

        def apply(self, ctx):
            ctx.data.setdefault("features", ["board", "meeting"])
            ctx.data.setdefault("created_app_ids", ["A1", "A2"])
            ctx.data.setdefault("slash_dropped", ["footer", "sethome"])
            ctx.data.setdefault("config_token", "xoxe-SECRET")  # must NOT be recorded

    monkeypatch.setattr(cli, "_build_steps", lambda: [_Seed()])

    state_dir = tmp_path / "state"
    af = tmp_path / "a.yaml"
    af.write_text(yaml.safe_dump({"features": ["board", "meeting"]}))
    res = CliRunner().invoke(cli.app, [
        "install", "--hermes-root", str(tmp_path / "h"),
        "--answers-file", str(af), "--non-interactive", "--state-dir", str(state_dir),
    ])
    assert res.exit_code == 0, res.stdout
    raw = json.loads((state_dir / "state.json").read_text())
    rec = raw["data"]["install_record"]
    assert rec["created_app_ids"] == ["A1", "A2"]
    assert sorted(rec["features"]) == ["board", "meeting"]
    assert rec["slash_dropped"] == ["footer", "sethome"]
    assert "config_token" not in rec
    assert "xoxe-SECRET" not in json.dumps(raw)


def test_install_record_merge_preserves_prior(tmp_path, monkeypatch):
    from hermes_slack_ext.wizard.engine import Step

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text(json.dumps(
        {"completed": [], "data": {"install_record": {"created_app_ids": ["OLD"], "features": ["board"]}}}))

    class _Empty(Step):
        id = "noop"

    monkeypatch.setattr(cli, "_build_steps", lambda: [_Empty()])
    af = tmp_path / "a.yaml"; af.write_text(yaml.safe_dump({"features": ["board"]}))
    CliRunner().invoke(cli.app, [
        "install", "--hermes-root", str(tmp_path / "h"),
        "--answers-file", str(af), "--non-interactive", "--state-dir", str(state_dir)])
    rec = json.loads((state_dir / "state.json").read_text())["data"]["install_record"]
    assert rec["created_app_ids"] == ["OLD"]
