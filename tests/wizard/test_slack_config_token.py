from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps import slack_config_token as T


def test_skips_when_no_meeting(tmp_path):
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data["features"] = ["board"]
    assert T.SlackConfigTokenStep().should_run(ctx) is False


def test_captures_token_without_printing(tmp_path, capsys):
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data["features"] = ["meeting"]
    prompts = ScriptedPrompts({"config_token": ["xoxe-secret"], "refresh_token": ["xoxe-1-refresh"]})
    T.SlackConfigTokenStep().prompt(ctx, prompts)
    assert ctx.data["config_token"] == "xoxe-secret"
    assert ctx.data["config_refresh_token"] == "xoxe-1-refresh"
    # 토큰 값이 stdout에 노출되지 않아야 함
    assert "xoxe-secret" not in capsys.readouterr().out
