import io
import json

import pytest

from hermes_slack_ext.core import slack_api as S


class _FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def _fake_urlopen(payload):
    def _open(req, *a, **k):
        _open.last_req = req
        return _FakeResp(json.dumps(payload).encode())
    return _open


def test_create_app_returns_credentials(monkeypatch):
    monkeypatch.setattr(S.urllib.request, "urlopen",
                        _fake_urlopen({"ok": True, "app_id": "A1", "credentials": {"client_id": "c"}}))
    out = S.create_app("xoxe-token", {"display_information": {"name": "X"}})
    assert out["app_id"] == "A1"


def test_non_ok_raises_slackapierror(monkeypatch):
    monkeypatch.setattr(S.urllib.request, "urlopen",
                        _fake_urlopen({"ok": False, "error": "invalid_manifest"}))
    with pytest.raises(S.SlackAPIError) as ei:
        S.create_app("t", {})
    assert ei.value.error == "invalid_manifest"


def test_auth_test_passes_token(monkeypatch):
    op = _fake_urlopen({"ok": True, "user_id": "U1", "team_id": "T1"})
    monkeypatch.setattr(S.urllib.request, "urlopen", op)
    out = S.auth_test("xoxb-abc")
    assert out["user_id"] == "U1"
    body = op.last_req.data.decode()
    assert "token=xoxb-abc" in body
