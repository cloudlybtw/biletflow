"""Shared test data helpers.

Use these instead of copied setup blocks — see CLAUDE.md's Testing section.
Factories flush (so server defaults are populated) but don't commit; the
caller's session owns the transaction.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, new_opaque_token
from app.modules.auth.models import UserToken, UserTokenPurpose
from app.modules.events.models import Event
from app.modules.notifications.models import Notification, NotificationChannel, NotificationType
from app.modules.orders.models import Attendee, Order, OrderItem, OrderStatus
from app.modules.organizers.models import OrganizerProfile, PayoutAccount, PayoutAccountStatus
from app.modules.ticketing.holds import SeatHold
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.users.models import StaffAssignment, StaffRole, User

DEFAULT_PASSWORD = "correct-horse-battery"
# Hashing is deliberately slow; reuse one hash for factory-made users.
_DEFAULT_PASSWORD_HASH = hash_password(DEFAULT_PASSWORD)


def unique_suffix() -> str:
    return secrets.token_hex(4)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}+{unique_suffix()}@example.com"


async def create_user(session: AsyncSession, **overrides: Any) -> User:
    fields: dict[str, Any] = {
        "email": unique_email(),
        "password_hash": _DEFAULT_PASSWORD_HASH,
        "full_name": "Test User",
    }
    fields.update(overrides)
    user = User(**fields)
    session.add(user)
    await session.flush()
    return user


async def create_notification(session: AsyncSession, user: User, **overrides: Any) -> Notification:
    fields = {
        "user_id": user.id,
        "type": NotificationType.EVENT_UPDATE,
        "channel": NotificationChannel.IN_APP,
        "template_key": "event_update.en",
        "payload": {"event_title": "Demo event"},
    }
    fields.update(overrides)
    row = Notification(**fields)
    session.add(row)
    await session.flush()
    return row


async def create_organizer(
    session: AsyncSession, user: User | None = None, **overrides: Any
) -> OrganizerProfile:
    if user is None:
        user = await create_user(session)
    fields: dict[str, Any] = {
        "user_id": user.id,
        "display_name": f"Organizer {unique_suffix()}",
        "contact_email": user.email,
    }
    fields.update(overrides)
    profile = OrganizerProfile(**fields)
    session.add(profile)
    await session.flush()
    return profile


async def create_user_token(
    session: AsyncSession,
    user: User,
    purpose: UserTokenPurpose = UserTokenPurpose.EMAIL_VERIFY,
    **overrides: Any,
) -> tuple[str, UserToken]:
    """Return (raw token, stored row); only the hash is persisted, as in production."""
    raw, token_hash = new_opaque_token()
    fields: dict[str, Any] = {
        "user_id": user.id,
        "purpose": purpose,
        "token_hash": token_hash,
        "expires_at": datetime.now(UTC) + timedelta(hours=24),
    }
    fields.update(overrides)
    token = UserToken(**fields)
    session.add(token)
    await session.flush()
    return raw, token


def auth_headers(user: User) -> dict[str, str]:
    """Authorization header with a fresh access token for `user`."""
    token, _ = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


async def create_verified_user(session: AsyncSession, **overrides: Any) -> User:
    return await create_user(session, email_verified_at=datetime.now(UTC), **overrides)


async def create_event(
    session: AsyncSession, organizer: OrganizerProfile | None = None, **overrides: Any
) -> uuid.UUID:
    """Insert an event row and return its id (keeps M1 permission tests compatible)."""
    if organizer is None:
        organizer = await create_organizer(session)
    starts_at = datetime.now(UTC) + timedelta(days=30)
    fields: dict[str, Any] = {
        "organizer_profile_id": organizer.id,
        "title": "Test Event",
        "slug": f"test-event-{unique_suffix()}",
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(hours=3),
    }
    fields.update(overrides)
    event = Event(**fields)
    session.add(event)
    await session.flush()
    return event.id


async def create_staff_assignment(
    session: AsyncSession, event_id: uuid.UUID, user: User, role: StaffRole, **overrides: Any
) -> StaffAssignment:
    assignment = StaffAssignment(event_id=event_id, user_id=user.id, role=role, **overrides)
    session.add(assignment)
    await session.flush()
    return assignment


async def create_payout_account(
    session: AsyncSession, organizer: OrganizerProfile, **overrides: Any
) -> PayoutAccount:
    fields: dict[str, Any] = {
        "organizer_profile_id": organizer.id,
        "provider": "biletflow_sim",
        "external_account_ref": f"KZ{secrets.randbelow(10**18):018d}",
        "account_holder_name": "Test Holder",
        "status": PayoutAccountStatus.ACTIVE,
    }
    fields.update(overrides)
    account = PayoutAccount(**fields)
    session.add(account)
    await session.flush()
    return account


async def create_ticket_type(
    session: AsyncSession, event_id: uuid.UUID, **overrides: Any
) -> TicketType:
    fields = {
        "event_id": event_id,
        "name": f"Standard {unique_suffix()}",
        "quantity_total": 100,
        "price_amount": 1000,
    }
    fields.update(overrides)
    ticket = TicketType(**fields)
    session.add(ticket)
    await session.flush()
    return ticket


async def create_seat_hold(
    session: AsyncSession,
    event_id: uuid.UUID,
    seat_id: uuid.UUID,
    ticket_type_id: uuid.UUID,
    user: User,
    **overrides: Any,
) -> SeatHold:
    fields: dict[str, Any] = {
        "event_id": event_id,
        "seat_id": seat_id,
        "ticket_type_id": ticket_type_id,
        "held_by_user_id": user.id,
        "session_token": f"test-{unique_suffix()}",
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
    }
    fields.update(overrides)
    hold = SeatHold(**fields)
    session.add(hold)
    await session.flush()
    return hold


async def create_issued_ticket(
    session: AsyncSession,
    event_id: uuid.UUID,
    buyer: User,
    *,
    ticket_type: TicketType | None = None,
    attendee_name: str | None = None,
    attendee_email: str | None = None,
    **overrides: Any,
) -> Ticket:
    """A canonical ticket for a completed free registration, with linked attendee/order."""
    if ticket_type is None:
        ticket_type = await create_ticket_type(session, event_id, price_amount=0)
    order = Order(
        event_id=event_id,
        buyer_user_id=buyer.id,
        buyer_email=buyer.email,
        buyer_name=buyer.full_name,
        order_number=f"TEST-{unique_suffix()}",
        status=OrderStatus.COMPLETED,
        placed_at=datetime.now(UTC),
    )
    session.add(order)
    await session.flush()
    item = OrderItem(
        order_id=order.id,
        ticket_type_id=ticket_type.id,
        quantity=1,
        unit_price_amount=0,
        line_total=0,
    )
    session.add(item)
    await session.flush()
    attendee = Attendee(
        order_item_id=item.id,
        user_id=buyer.id,
        full_name=attendee_name or buyer.full_name,
        email=attendee_email or buyer.email,
    )
    session.add(attendee)
    await session.flush()
    fields = {
        "ticket_code": f"BFT-{unique_suffix().upper()}",
        "qr_token": "bft_" + secrets.token_urlsafe(32),
        "event_id": event_id,
        "order_item_id": item.id,
        "ticket_type_id": ticket_type.id,
        "attendee_id": attendee.id,
    }
    fields.update(overrides)
    ticket = Ticket(**fields)
    session.add(ticket)
    ticket_type.quantity_sold += 1
    await session.flush()
    return ticket


async def create_reporting_context(session):
    """Published event and role matrix shared by analytics/history/admin tests."""
    from types import SimpleNamespace

    from app.modules.events.models import EventStatus, PaidSalesStatus
    from app.modules.users.models import PlatformRole

    owner = await create_verified_user(session)
    profile = await create_organizer(session, owner)
    event_id = await create_event(
        session, profile, status=EventStatus.PUBLISHED, paid_sales_status=PaidSalesStatus.ACTIVE
    )
    ticket_type = await create_ticket_type(session, event_id, price_amount=1000, name="Standard")
    buyer = await create_verified_user(session)
    co = await create_verified_user(session)
    assignment = await create_staff_assignment(session, event_id, co, StaffRole.CO_ORGANIZER)
    event_admin = await create_verified_user(session)
    await create_staff_assignment(session, event_id, event_admin, StaffRole.EVENT_ADMIN)
    support = await create_verified_user(session)
    await create_staff_assignment(session, event_id, support, StaffRole.SUPPORT_AGENT)
    admin = await create_verified_user(session, platform_role=PlatformRole.PLATFORM_ADMIN)
    await session.commit()
    return SimpleNamespace(
        owner=owner,
        profile=profile,
        event_id=event_id,
        ticket_type=ticket_type,
        buyer=buyer,
        co=co,
        assignment=assignment,
        event_admin=event_admin,
        support=support,
        admin=admin,
    )


async def complete_purchase(client, context, **checkout_options):
    from tests.orders.helpers import pay, placed_order, simulate

    order = await placed_order(client, context, **checkout_options)
    if order["total_amount"]:
        payment = await pay(client, context, order["id"])
        result = await simulate(client, context, payment["id"])
        assert result.status_code == 200, result.text
    response = await client.get(
        f"/api/v1/orders/{order['id']}", headers=auth_headers(context.buyer)
    )
    assert response.status_code == 200, response.text
    return response.json()
