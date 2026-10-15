import asyncio
import smtplib
import threading
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.jobs import expire_orders
from app.jobs import send_notifications as sender
from app.main import create_app
from app.modules.notifications.models import Notification, NotificationChannel, NotificationType
from app.modules.notifications.templates import render
from tests.factories import auth_headers, create_notification, create_verified_user


@pytest.mark.parametrize("kind", list(NotificationType))
@pytest.mark.parametrize("locale", ["kk", "ru", "en"])
async def test_every_notification_type_has_an_english_fallback_without_public_auth_links(
    kind, locale
):
    payload = {
        "verify_url": "https://example.com/verify?token=secret",
        "reset_url": "https://example.com/reset?token=secret",
        "amount": 1000,
        "status": "cancelled",
        "case_number": "BFS-123",
    }
    title, body = render(kind, payload, locale)
    assert title and body and "secret" not in body
    if kind in {
        NotificationType.REFUND_COMPLETED,
        NotificationType.PAYMENT_FAILED,
        NotificationType.PAYOUT_STATUS,
    }:
        assert "simulated" in body and "No real money" in body


@pytest.mark.parametrize(
    "kind,key",
    [
        (NotificationType.ACCOUNT_VERIFICATION, "verify_url"),
        (NotificationType.PASSWORD_RESET, "reset_url"),
    ],
)
async def test_successful_delivery_scrubs_auth_secrets_after_smtp_acceptance(
    db_session, test_sessionmaker, kind, key
):
    user = await create_verified_user(db_session)
    row = await create_notification(
        db_session,
        user,
        channel=NotificationChannel.EMAIL,
        type=kind,
        payload={
            key: "https://example.com/action?token=raw-secret",
            "nested": {"raw_token": "other-secret", "safe": 1},
            "future_url": "https://example.com/action?token=future-secret",
        },
    )
    await db_session.commit()
    seen = []

    async def send(message):
        stored = await db_session.get(Notification, row.id, populate_existing=True)
        assert key in stored.payload  # Remove only after a successful send.
        seen.append(message)

    assert await sender.deliver_batch(session_factory=test_sessionmaker, send=send) == 1
    current = await db_session.get(Notification, row.id, populate_existing=True)
    assert (
        current.status == "sent" and current.sent_at is not None and current.error_message is None
    )
    assert "secret" not in str(current.payload) and current.payload["nested"] == {"safe": 1}
    assert "raw-secret" in seen[0].get_content() and seen[0]["To"] == user.email
    assert seen[0]["Content-Language"] == "en"
    assert await sender.deliver_batch(session_factory=test_sessionmaker, send=send) == 0


async def test_failed_delivery_isolated_keeps_retry_payload_and_does_not_log_secret(
    db_session, test_sessionmaker
):
    user = await create_verified_user(db_session)
    bad = await create_notification(
        db_session,
        user,
        channel=NotificationChannel.EMAIL,
        type=NotificationType.PASSWORD_RESET,
        payload={"reset_url": "https://example.com/?token=secret"},
    )
    good = await create_notification(db_session, user, channel=NotificationChannel.EMAIL)
    await db_session.commit()

    async def send(message):
        if "Reset" in message["Subject"]:
            raise smtplib.SMTPException("secret reset link in provider error")

    assert await sender.deliver_batch(session_factory=test_sessionmaker, send=send) == 1
    bad = await db_session.get(Notification, bad.id, populate_existing=True)
    assert bad.status == "failed" and "secret" not in bad.error_message and bad.payload["reset_url"]
    assert (await db_session.get(Notification, good.id, populate_existing=True)).status == "sent"
    await db_session.execute(
        update(Notification).where(Notification.id == bad.id).values(status="queued")
    )
    await db_session.commit()
    assert await sender.deliver_batch(session_factory=test_sessionmaker, send=AsyncMock()) == 1


async def test_overlapping_senders_claim_a_queued_email_once(db_session, test_sessionmaker):
    user = await create_verified_user(db_session)
    await create_notification(db_session, user, channel=NotificationChannel.EMAIL)
    await db_session.commit()
    sent = []

    async def send(message):
        sent.append(message)
        await asyncio.sleep(0.02)

    counts = await asyncio.gather(
        *(sender.deliver_batch(session_factory=test_sessionmaker, send=send) for _ in range(3))
    )
    assert sum(counts) == len(sent) == 1


async def test_bounded_delivery_ignores_in_app_and_failed_rows(db_session, test_sessionmaker):
    user = await create_verified_user(db_session)
    for _ in range(3):
        await create_notification(db_session, user, channel=NotificationChannel.EMAIL)
    in_app = await create_notification(db_session, user)
    failed = await create_notification(
        db_session, user, channel=NotificationChannel.EMAIL, status="failed"
    )
    await db_session.commit()
    send = AsyncMock()
    assert (
        await sender.deliver_batch(session_factory=test_sessionmaker, batch_size=2, send=send) == 2
    )
    assert send.await_count == 2
    assert (
        await db_session.get(Notification, in_app.id, populate_existing=True)
    ).status == "queued"
    assert (
        await db_session.get(Notification, failed.id, populate_existing=True)
    ).status == "failed"


async def test_smtp_runs_in_a_thread_with_a_timeout_and_expected_headers(monkeypatch):
    main_thread = threading.get_ident()
    calls = []

    class SMTP:
        def __init__(self, host, port, timeout):
            assert threading.get_ident() != main_thread
            calls.append((host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, message):
            calls.append(message)

    monkeypatch.setattr(sender.smtplib, "SMTP", SMTP)
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = "Demo"
    await sender.send_email(message)
    settings = get_settings()
    assert calls == [
        (settings.smtp_host, settings.smtp_port, settings.smtp_timeout_seconds),
        message,
    ]


async def test_inbox_lists_only_my_in_app_rows_and_mark_read_is_idempotent(client, db_session):
    user, other = await create_verified_user(db_session), await create_verified_user(db_session)
    own = await create_notification(
        db_session,
        user,
        payload={"verify_url": "secret", "raw_token": "hidden", "event_title": "Demo"},
    )
    await create_notification(db_session, user)
    email = await create_notification(db_session, user, channel=NotificationChannel.EMAIL)
    foreign = await create_notification(db_session, other)
    await db_session.commit()
    headers = auth_headers(user)
    response = await client.get("/api/v1/notifications?limit=1&offset=1", headers=headers)
    assert (
        response.status_code == 200
        and response.json()["total"] == 2
        and len(response.json()["items"]) == 1
    )
    assert (
        "secret" not in response.text
        and "hidden" not in response.text
        and "payload" not in response.text
    )
    path = f"/api/v1/notifications/{own.id}/read"
    first = await client.post(path, headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "read"
    second = await client.post(path, headers=headers)
    assert second.json()["read_at"] == first.json()["read_at"]
    assert (await client.get("/api/v1/notifications?unread_only=true", headers=headers)).json()[
        "total"
    ] == 1
    for row in [email, foreign]:
        assert (
            await client.post(f"/api/v1/notifications/{row.id}/read", headers=headers)
        ).status_code == 404
    assert (await client.get("/api/v1/notifications")).status_code == 401
    assert (await client.post(path)).status_code == 401


async def test_lifespan_sends_queued_notification_and_stops(
    db_session, test_sessionmaker, monkeypatch
):
    user = await create_verified_user(db_session)
    row = await create_notification(db_session, user, channel=NotificationChannel.EMAIL)
    await db_session.commit()
    sent = asyncio.Event()

    async def send(message):
        sent.set()

    monkeypatch.setattr(sender, "send_email", send)
    app = create_app(session_factory=test_sessionmaker)
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(sent.wait(), timeout=5)
        # Wait for the whole pass to commit rather than racing task cancellation.
        for _ in range(100):
            await db_session.rollback()
            current = await db_session.get(Notification, row.id, populate_existing=True)
            if current.status == "sent":
                break
            await asyncio.sleep(0.01)
        assert current.status == "sent"
    assert app.state.background_task.cancelled()


async def test_notification_pass_runs_even_when_expiry_fails(test_sessionmaker, monkeypatch):
    deliver = AsyncMock(return_value=0)
    monkeypatch.setattr(
        expire_orders, "sweep_expired", AsyncMock(side_effect=RuntimeError("db error"))
    )
    monkeypatch.setattr(expire_orders, "deliver_batch", deliver)
    monkeypatch.setattr(
        expire_orders,
        "asyncio",
        type("Loop", (), {"sleep": AsyncMock(side_effect=asyncio.CancelledError())}),
    )
    with pytest.raises(asyncio.CancelledError):
        await expire_orders.run(once=False, interval_seconds=30, session_factory=test_sessionmaker)
    deliver.assert_awaited_once_with(session_factory=test_sessionmaker)


@pytest.mark.parametrize("fail_outbox", [False, True])
async def test_event_edit_notifies_each_active_buyer_once_and_noop_sends_nothing(
    client, db_session, monkeypatch, fail_outbox
):
    from app.modules.events import service as events
    from app.modules.events.models import EventStatus
    from tests.factories import create_event, create_issued_ticket, create_organizer

    owner = await create_verified_user(db_session)
    profile = await create_organizer(db_session, owner)
    event_id = await create_event(db_session, profile, status=EventStatus.PUBLISHED)
    buyer = await create_verified_user(db_session)
    await create_issued_ticket(db_session, event_id, buyer)
    await create_issued_ticket(db_session, event_id, buyer)
    await db_session.commit()
    path = f"/api/v1/events/{event_id}"
    if fail_outbox:

        async def fail(*args, **kwargs):
            raise RuntimeError("outbox failure")

        monkeypatch.setattr(events.notifications, "enqueue", fail)
        response = await client.patch(
            path, headers=auth_headers(owner), json={"title": "New event title"}
        )
        assert response.status_code == 500
        detail = await client.get(path, headers=auth_headers(owner))
        assert detail.json()["title"] == "Test Event"
        assert list((await db_session.scalars(select(Notification))).all()) == []
        return
    for _ in range(2):
        result = await client.patch(
            path, headers=auth_headers(owner), json={"title": "New event title"}
        )
        assert result.status_code == 200, result.text
    rows = (
        await db_session.scalars(
            select(Notification).where(Notification.related_entity_type == "event")
        )
    ).all()
    assert len(rows) == 1 and rows[0].user_id == buyer.id
    assert rows[0].payload["changed_fields"] == ["title"]


async def test_shutdown_keeps_email_locked_until_smtp_thread_finishes(
    db_session, test_sessionmaker, monkeypatch
):
    user = await create_verified_user(db_session)
    row = await create_notification(db_session, user, channel=NotificationChannel.EMAIL)
    await db_session.commit()
    started = asyncio.Event()
    finish = threading.Event()
    loop = asyncio.get_running_loop()

    def smtp_send(message):
        loop.call_soon_threadsafe(started.set)
        assert finish.wait(timeout=5)

    monkeypatch.setattr(sender, "_smtp_send", smtp_send)
    task = asyncio.create_task(sender.deliver_batch(session_factory=test_sessionmaker))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        assert await sender.deliver_batch(session_factory=test_sessionmaker, send=AsyncMock()) == 0
        assert not task.done()
    finally:
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    # SMTP acceptance followed by shutdown is intentionally at-least-once.
    assert (await db_session.get(Notification, row.id, populate_existing=True)).status == "queued"


@pytest.mark.parametrize("foreign", [False, True])
async def test_ticket_delivery_attaches_only_buyers_canonical_pdf(
    db_session, test_sessionmaker, foreign
):
    from tests.factories import create_event, create_issued_ticket

    buyer = await create_verified_user(db_session)
    other = await create_verified_user(db_session)
    event_id = await create_event(db_session)
    ticket = await create_issued_ticket(db_session, event_id, other if foreign else buyer)
    row = await create_notification(
        db_session,
        buyer,
        type=NotificationType.TICKET_DELIVERY,
        channel=NotificationChannel.EMAIL,
        payload={"ticket_ids": [str(ticket.id)]},
    )
    await db_session.commit()
    messages = []

    async def send(message):
        messages.append(message)

    count = await sender.deliver_batch(session_factory=test_sessionmaker, send=send)
    if foreign:
        assert count == 0 and messages == []
        assert (
            await db_session.get(Notification, row.id, populate_existing=True)
        ).status == "failed"
    else:
        assert count == 1 and messages[0]["To"] == buyer.email
        attachments = list(messages[0].iter_attachments())
        assert (
            len(attachments) == 1 and attachments[0].get_filename() == ticket.ticket_code + ".pdf"
        )
        assert attachments[0].get_payload(decode=True).startswith(b"%PDF")
        assert messages[0]["Content-Language"] == "en"
