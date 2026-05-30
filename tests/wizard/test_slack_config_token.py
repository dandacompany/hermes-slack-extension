from hermes_slack_ext.wizard.engine import WizardContext
from hermes_slack_ext.wizard.prompts import ScriptedPrompts
from hermes_slack_ext.wizard.steps import slack_config_token as T


def test_skips_when_no_meeting(tmp_path):
    ctx = WizardContext(hermes_root=tmp_path)
    ctx.data["features"] = ["board"]
    assert T.SlackConfigTokenStep().should_run(ctx) is False


def test_captures_token_without_printing(tmp_path, capsys):
    # 헤드리스(non_interactive): 컨텍스트 키는 answers-file 주입에 의존 → 프롬프트 안 함.
    ctx = WizardContext(hermes_root=tmp_path, non_interactive=True)
    ctx.data["features"] = ["meeting"]
    prompts = ScriptedPrompts({"config_token": ["xoxe-secret"], "refresh_token": ["xoxe-1-refresh"]})
    T.SlackConfigTokenStep().prompt(ctx, prompts)
    assert ctx.data["config_token"] == "xoxe-secret"
    assert ctx.data["config_refresh_token"] == "xoxe-1-refresh"
    # 토큰 값이 stdout에 노출되지 않아야 함
    assert "xoxe-secret" not in capsys.readouterr().out


def test_interactive_collects_context_when_missing(tmp_path):
    # 대화형(non_interactive=False): 누락된 채널/유저/모더레이터봇 id를 묻는다.
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
    # 이미 주입된 값은 다시 묻지 않는다(프롬프트 큐가 비어도 PromptExhausted 안 남).
    ctx = WizardContext(hermes_root=tmp_path, non_interactive=False)
    ctx.data.update({"features": ["meeting"], "channel_id": "Cpre",
                     "human_user_id": "Upre", "moderator_bot_user_id": "Bpre"})
    prompts = ScriptedPrompts({"config_token": ["xoxe-s"], "refresh_token": ["xoxe-r"]})
    T.SlackConfigTokenStep().prompt(ctx, prompts)
    assert ctx.data["channel_id"] == "Cpre"
