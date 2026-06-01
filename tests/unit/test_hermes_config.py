import yaml

from hermes_slack_ext.core import hermes as H


def test_enable_toolset_no_config(tmp_path):
    assert H.enable_toolset(tmp_path / "missing.yaml", "kanban") == "no-config"


def test_enable_toolset_adds_to_block_list(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: x\ntoolsets:\n- hermes-cli\nslack:\n  channel_prompts: {}\n", encoding="utf-8")
    assert H.enable_toolset(cfg, "kanban") == "enabled"
    data = yaml.safe_load(cfg.read_text())
    assert data["toolsets"] == ["hermes-cli", "kanban"]
    # other keys survive the round-trip
    assert data["model"] == "x" and "slack" in data


def test_enable_toolset_adds_to_flow_list(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("toolsets: [hermes-cli]\n", encoding="utf-8")
    assert H.enable_toolset(cfg, "kanban") == "enabled"
    assert "kanban" in yaml.safe_load(cfg.read_text())["toolsets"]


def test_enable_toolset_is_idempotent(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("toolsets:\n- hermes-cli\n- kanban\n", encoding="utf-8")
    assert H.enable_toolset(cfg, "kanban") == "already"
    assert yaml.safe_load(cfg.read_text())["toolsets"].count("kanban") == 1


def test_enable_toolset_when_no_toolsets_key(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: x\n", encoding="utf-8")
    assert H.enable_toolset(cfg, "kanban") == "enabled"
    assert yaml.safe_load(cfg.read_text())["toolsets"] == ["kanban"]


def test_kanban_toolset_enabled_true_false(tmp_path):
    on = tmp_path / "on.yaml"
    on.write_text("toolsets: [hermes-cli, kanban]\n", encoding="utf-8")
    off = tmp_path / "off.yaml"
    off.write_text("toolsets: [hermes-cli]\n", encoding="utf-8")
    assert H.kanban_toolset_enabled(on) is True
    assert H.kanban_toolset_enabled(off) is False
    # missing / unparseable config is treated as not-enabled, never raises
    assert H.kanban_toolset_enabled(tmp_path / "nope.yaml") is False
