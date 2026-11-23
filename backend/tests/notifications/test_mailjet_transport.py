import base64
import io
import json
from email.message import EmailMessage

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.jobs import send_notifications as sender


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _message() -> EmailMessage:
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "to@example.test"
    message["Subject"] = "Hello"
    message["Message-ID"] = "<abc@biletflow.local>"
    message.set_content("Plain body")
    message.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="t.pdf")
    return message


def _settings() -> Settings:
    return Settings(_env_file=None, mailjet_api_key="key", mailjet_api_secret="secret")


def test_mailjet_payload_carries_body_and_attachments():
    payload = sender._mailjet_payload(_message())["Messages"][0]
    assert payload["From"] == {"Email": "sender@example.test"}
    assert payload["To"] == [{"Email": "to@example.test"}]
    assert payload["TextPart"].strip() == "Plain body"
    assert payload["CustomID"] == "abc@biletflow.local"
    attachment = payload["Attachments"][0]
    assert attachment["Filename"] == "t.pdf"
    assert base64.b64decode(attachment["Base64Content"]) == b"%PDF-1.4"


def test_mailjet_send_uses_https_basic_auth_and_succeeds(monkeypatch):
    monkeypatch.setattr(sender, "get_settings", _settings)
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"], seen["auth"] = request.full_url, request.get_header("Authorization")
        return _Response(json.dumps({"Messages": [{"Status": "success"}]}).encode())

    monkeypatch.setattr(sender, "urlopen", fake_urlopen)
    sender._mailjet_send(_message())
    assert seen["url"].startswith("https://")
    assert seen["auth"] == "Basic " + base64.b64encode(b"key:secret").decode()


def test_mailjet_rejection_raises_so_the_row_is_marked_failed(monkeypatch):
    monkeypatch.setattr(sender, "get_settings", _settings)
    monkeypatch.setattr(
        sender, "urlopen", lambda *a, **k: _Response(b'{"Messages": [{"Status": "error"}]}')
    )
    with pytest.raises(RuntimeError):
        sender._mailjet_send(_message())


def test_transport_prefers_mailjet_only_when_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(sender, "_mailjet_send", lambda m: calls.append("mailjet"))
    monkeypatch.setattr(sender, "_smtp_send", lambda m: calls.append("smtp"))
    monkeypatch.setattr(sender, "get_settings", _settings)
    sender._transport(_message())
    monkeypatch.setattr(sender, "get_settings", lambda: Settings(_env_file=None))
    sender._transport(_message())
    assert calls == ["mailjet", "smtp"]


def test_mailjet_requires_both_key_and_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mailjet_api_key="key")
