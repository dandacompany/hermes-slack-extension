from __future__ import annotations

import json
import urllib.parse
import urllib.request

_API = "https://slack.com/api/"


class SlackAPIError(RuntimeError):
    """Raised when a Slack API response has ok=false."""

    def __init__(self, method: str, error: str, response: dict | None = None):
        super().__init__(f"{method} failed: {error}")
        self.method = method
        self.error = error
        self.response = response or {}


def _post(method: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        _API + method, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode())
    if not body.get("ok"):
        raise SlackAPIError(method, body.get("error", "unknown"), body)
    return body


def rotate_tokens(refresh_token: str) -> dict:
    return _post("tooling.tokens.rotate", {"refresh_token": refresh_token})


def validate_manifest(config_token: str, manifest: dict) -> dict:
    return _post("apps.manifest.validate", {"token": config_token, "manifest": json.dumps(manifest)})


def create_app(config_token: str, manifest: dict) -> dict:
    return _post("apps.manifest.create", {"token": config_token, "manifest": json.dumps(manifest)})


def update_app(config_token: str, app_id: str, manifest: dict) -> dict:
    return _post("apps.manifest.update",
                 {"token": config_token, "app_id": app_id, "manifest": json.dumps(manifest)})


def delete_app(config_token: str, app_id: str) -> dict:
    return _post("apps.manifest.delete", {"token": config_token, "app_id": app_id})


def auth_test(bot_token: str) -> dict:
    return _post("auth.test", {"token": bot_token})


def conversations_join(bot_token: str, channel: str) -> dict:
    return _post("conversations.join", {"token": bot_token, "channel": channel})
