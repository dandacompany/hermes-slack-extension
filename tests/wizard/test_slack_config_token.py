from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps import slack_config_token as T


def test_skips_when_no_meeting(tmp_path):
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data["features"] = ["board"]
    assert T.SlackConfigTokenStep().should_run(ctx) is False


def test_captures_token_without_printing(tmp_path, capsys):
    # headless (non_interactive): context keys rely on answers-file injection -> no prompting.
    ctx = WizardContext(hermes_root=tmp_path, non_interactive=True)
    ctx.data["features"] = ["meeting"]
    prompts = ScriptedPrompts({"config_token": ["xoxe-secret"], "refresh_token": ["xoxe-1-refresh"]})
    T.SlackConfigTokenStep().prompt(ctx, prompts)
    assert ctx.data["config_token"] == "xoxe-secret"
    assert ctx.data["config_refresh_token"] == "xoxe-1-refresh"
    # the token value must not be exposed in stdout
    assert "xoxe-secret" not in capsys.readouterr().out


def test_interactive_collects_context_when_missing(tmp_path):
    # interactive (non_interactive=False): prompts for missing channel/user/moderator-bot ids.
    ctx = WizardContext(hermes_root=tmp_path, non_interactive=False)
    ctx.data["features"] = ["meeting"]
    prompts = ScriptedPrompts({
        "config_token": ["xoxe-s"], "refresh_token": ["xoxe-r"],
        "channel_id": ["C9"], "human_user_id": ["U9"], "moderator_bot_user_id": ["Bmod9"],
    })
    T.SlackConfigTokenStep().prompt(ctx, prompts)
    assert ctx.data["channel_id"] == "C9"
    assert ctx.data["human_user_id"] == "U9"
    assert ctx.data["moderator_bot_user_id"] == "Bmod9"


def test_interactive_skips_already_provided_context(tmp_path):
    # already-injected values are not asked again (no PromptExhausted even with an empty prompt queue).
    ctx = WizardContext(hermes_root=tmp_path, non_interactive=False)
    ctx.data.update({"features": ["meeting"], "channel_id": "Cpre",
                     "human_user_id": "Upre", "moderator_bot_user_id": "Bpre"})
    prompts = ScriptedPrompts({"config_token": ["xoxe-s"], "refresh_token": ["xoxe-r"]})
    T.SlackConfigTokenStep().prompt(ctx, prompts)
    assert ctx.data["channel_id"] == "Cpre"
