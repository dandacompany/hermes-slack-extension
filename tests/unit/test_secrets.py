import os
import stat

from hermes_slack_ext.core import secrets as Sec


def test_write_env_sets_keys_and_mode(tmp_path):
    env = tmp_path / "profile.env"
    Sec.write_env(env, {"SLACK_BOT_TOKEN": "xoxb-1", "SLACK_APP_TOKEN": "xapp-1"})
    text = env.read_text()
    assert "SLACK_BOT_TOKEN=xoxb-1" in text
    assert "SLACK_APP_TOKEN=xapp-1" in text
    mode = stat.S_IMODE(os.stat(env).st_mode)
    assert mode == 0o600


def test_write_env_merges_existing_keys(tmp_path):
    env = tmp_path / "p.env"
    env.write_text("EXISTING=1\nSLACK_BOT_TOKEN=old\n")
    Sec.write_env(env, {"SLACK_BOT_TOKEN": "new"})
    text = env.read_text()
    assert "EXISTING=1" in text
    assert "SLACK_BOT_TOKEN=new" in text
    assert "old" not in text


def test_write_env_overwrite_tightens_loose_mode(tmp_path):
    # Even if the existing file has a loose 0644 mode, after the atomic replace the final mode must be 0600.
    env = tmp_path / "loose.env"
    env.write_text("SLACK_BOT_TOKEN=old\n")
    os.chmod(env, 0o644)
    Sec.write_env(env, {"SLACK_BOT_TOKEN": "new"})
    assert stat.S_IMODE(os.stat(env).st_mode) == 0o600
    assert "new" in env.read_text()


def test_write_env_leaves_no_temp_files(tmp_path):
    # The temp file (.env.*) used for the atomic write must not be left behind.
    env = tmp_path / "p.env"
    Sec.write_env(env, {"SLACK_BOT_TOKEN": "xoxb-1"})
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "p.env"]
    assert leftovers == [], f"leftover temp files: {leftovers}"


def test_mask_hides_middle():
    assert Sec.mask("xoxb-123456789") == "xoxb-123***"
    assert Sec.mask("") == "<empty>"


def test_verify_keys_present(tmp_path):
    env = tmp_path / "p.env"
    env.write_text("SLACK_BOT_TOKEN=x\n")
    assert Sec.verify_keys_present(env, ["SLACK_BOT_TOKEN"]) == {"SLACK_BOT_TOKEN": True}
    assert Sec.verify_keys_present(env, ["SLACK_APP_TOKEN"]) == {"SLACK_APP_TOKEN": False}
