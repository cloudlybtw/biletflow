"""Bounded outbox delivery. Row locks prevent overlapping workers from double sending.

SMTP and the database cannot commit atomically: a crash after SMTP acceptance
can cause redelivery. Failed rows retain their payload for explicit operator retry.
"""

import asyncio
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from app.modules.notifications.templates import render
from app.modules.tickets import service as tickets
from app.modules.tickets.pdf import render as render_pdf
from app.modules.users.models import User


def scrub_secrets(value):
    if isinstance(value, dict):
        return {
            key: scrub_secrets(item)
            for key, item in value.items()
            if "token" not in key.lower()
            and "password" not in key.lower()
            and key not in {"verify_url", "reset_url"}
        }
    if isinstance(value, list):
        return [scrub_secrets(item) for item in value]
    if isinstance(value, str):
        try:
            keys = [key.lower() for key, _ in parse_qsl(urlsplit(value).query)]
        except ValueError:
            return value
        if any("token" in key or "password" in key for key in keys):
            return "[removed]"
    return value


def _smtp_send(message: EmailMessage) -> None:
    settings = get_settings()
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as smtp:
        smtp.send_message(message)


async def send_email(message: EmailMessage) -> None:
    # Shield the bounded thread so shutdown cannot release its row lock while
    # SMTP is still sending. Cancellation is propagated after that send finishes.
    task = asyncio.create_task(asyncio.to_thread(_smtp_send, message))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


async def deliver_batch(*, session_factory=AsyncSessionLocal, batch_size=20, send=None) -> int:
    send = send or send_email
    async with session_factory() as session:
        ids = list(
            (
                await session.scalars(
                    select(Notification.id)
                    .where(
                        Notification.channel == NotificationChannel.EMAIL,
                        Notification.status == NotificationStatus.QUEUED,
                    )
                    .order_by(Notification.created_at, Notification.id)
                    .limit(batch_size)
                )
            ).all()
        )
    delivered = 0
    for notification_id in ids:
        async with session_factory() as session:
            row = await session.scalar(
                select(Notification)
                .where(
                    Notification.id == notification_id,
                    Notification.status == NotificationStatus.QUEUED,
                )
                .with_for_update(skip_locked=True)
            )
            if row is None:
                continue
            user = await session.get(User, row.user_id)
            try:
                subject, body = render(row.type, row.payload, user.locale, private=True)
                message = EmailMessage()
                message["From"] = get_settings().smtp_from
                message["To"] = row.payload.get("to_email") or user.email
                message["Subject"] = subject
                message["Message-ID"] = f"<{row.id}@biletflow.local>"
                message.set_content(body)
                if row.type == NotificationType.TICKET_DELIVERY:
                    ids = row.payload.get("ticket_ids", [])
                    if not ids:
                        raise ValueError("Ticket delivery requires issued tickets.")
                    for ticket_id in dict.fromkeys(ids):
                        ticket = await tickets.detail(session, user, uuid.UUID(ticket_id))
                        pdf = await asyncio.to_thread(render_pdf, ticket)
                        message.add_attachment(
                            pdf,
                            maintype="application",
                            subtype="pdf",
                            filename=f"{ticket.ticket_code}.pdf",
                        )
                message["Content-Language"] = "en"
                await send(message)
            except Exception as exc:
                row.status = NotificationStatus.FAILED
                # Exception text may contain an authentication URL or SMTP body.
                row.error_message = f"Delivery failed ({type(exc).__name__})."
            else:
                row.status = NotificationStatus.SENT
                row.sent_at = datetime.now(UTC)
                row.error_message = None
                row.payload = scrub_secrets(row.payload)
                delivered += 1
            await session.commit()
    return delivered
