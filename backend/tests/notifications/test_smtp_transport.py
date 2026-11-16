import ssl
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.jobs import send_notifications as sender


@pytest.mark.parametrize("mode", ["none", "starttls", "ssl"])
def test_smtp_transport_validates_certificates_and_authenticates_after_tls(monkeypatch, mode):
    settings = Settings(
        _env_file=None,
        smtp_host="smtp.example.test",
        smtp_port=465 if mode == "ssl" else 587,
        smtp_security=mode,
        smtp_username="demo-user" if mode != "none" else None,
        smtp_password="private-test-password" if mode != "none" else None,
    )
    monkeypatch.setattr(sender, "get_settings", lambda: settings)
    factory = MagicMock()
    smtp = factory.return_value.__enter__.return_value
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL" if mode == "ssl" else "SMTP", factory)
    other = MagicMock()
    monkeypatch.setattr(sender.smtplib, "SMTP" if mode == "ssl" else "SMTP_SSL", other)
    message = EmailMessage()
    sender._smtp_send(message)
    other.assert_not_called()
    if mode == "starttls":
        assert [call[0] for call in smtp.method_calls] == [
            "ehlo",
            "starttls",
            "ehlo",
            "login",
            "send_message",
        ]
        context = smtp.starttls.call_args.kwargs["context"]
    elif mode == "ssl":
        assert [call[0] for call in smtp.method_calls] == ["login", "send_message"]
        context = factory.call_args.kwargs["context"]
    else:
        smtp.login.assert_not_called()
        smtp.starttls.assert_not_called()
        return
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    smtp.login.assert_called_once_with("demo-user", "private-test-password")
    assert "private-test-password" not in repr(settings)


@pytest.mark.parametrize(
    "fields",
    [
        {"smtp_username": "user"},
        {"smtp_password": "password"},
        {"smtp_username": "user", "smtp_password": "password", "smtp_security": "none"},
    ],
)
def test_smtp_rejects_partial_or_plaintext_authentication(fields):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **fields)


def test_starttls_failure_never_sends_credentials_or_message(monkeypatch):
    settings = Settings(
        _env_file=None, smtp_security="starttls", smtp_username="user", smtp_password="secret"
    )
    monkeypatch.setattr(sender, "get_settings", lambda: settings)
    factory = MagicMock()
    monkeypatch.setattr(sender.smtplib, "SMTP", factory)
    smtp = factory.return_value.__enter__.return_value
    smtp.starttls.side_effect = OSError("TLS failed")
    with pytest.raises(OSError, match="TLS failed"):
        sender._smtp_send(EmailMessage())
    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()
