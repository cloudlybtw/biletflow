"""Demo accounts for the web and mobile teams: `uv run python -m app.scripts.seed_demo`.

Idempotent: existing rows (matched by email) are left alone, so it's safe to
re-run. Demo events, inventory, campaign, orders, support and check-in use the same services as the API.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.models  # noqa: F401  (registers every mapper)
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.modules.organizers.models import (
    OrganizerProfile,
    PayoutAccount,
    PayoutAccountStatus,
    VerificationStatus,
)
from app.modules.organizers.service import SIMULATED_PAYOUT_PROVIDER
from app.modules.users.models import PlatformRole, User

DEMO_PASSWORD = "demo-pass-2026"


@dataclass(frozen=True)
class DemoAccount:
    email: str
    full_name: str
    role: str
    platform_role: PlatformRole = PlatformRole.ATTENDEE


DEMO_ACCOUNTS = (
    DemoAccount(
        "admin@example.com", "Platform Admin", "platform admin", PlatformRole.PLATFORM_ADMIN
    ),
    DemoAccount("organizer@example.com", "Dana Organizer", "organizer (paid-sales ready)"),
    DemoAccount("attendee@example.com", "Arman Attendee", "attendee"),
    # Assigned to both seeded events for the Flutter check-in rehearsal.
    DemoAccount("eventadmin@example.com", "Iliyas Scanner", "event admin (Flutter check-in)"),
)
ORGANIZER_EMAIL = "organizer@example.com"


async def seed(session: AsyncSession) -> None:
    password_hash = hash_password(DEMO_PASSWORD)
    users: dict[str, User] = {}
    for account in DEMO_ACCOUNTS:
        user = await session.scalar(select(User).where(User.email == account.email))
        if user is None:
            user = User(
                email=account.email,
                password_hash=password_hash,
                full_name=account.full_name,
                locale="ru",
                platform_role=account.platform_role,
                email_verified_at=datetime.now(UTC),
            )
            session.add(user)
            await session.flush()
        users[account.email] = user

    organizer = users[ORGANIZER_EMAIL]
    profile = await session.scalar(
        select(OrganizerProfile).where(OrganizerProfile.user_id == organizer.id)
    )
    if profile is None:
        profile = OrganizerProfile(
            user_id=organizer.id,
            display_name="Almaty Live Events",
            contact_email=organizer.email,
            contact_phone="+77270000000",
            description="Demo organizer for BiletFlow.",
            verification_status=VerificationStatus.VERIFIED,
            verified_at=datetime.now(UTC),
        )
        session.add(profile)
        await session.flush()

    has_payout_account = await session.scalar(
        select(PayoutAccount.id).where(PayoutAccount.organizer_profile_id == profile.id)
    )
    if has_payout_account is None:
        session.add(
            PayoutAccount(
                organizer_profile_id=profile.id,
                provider=SIMULATED_PAYOUT_PROVIDER,
                external_account_ref="KZ00DEMO0000000000001",
                account_holder_name=organizer.full_name,
                status=PayoutAccountStatus.ACTIVE,
                is_default=True,
                is_simulated=True,
            )
        )
    await session.commit()
    await seed_scenarios(session, users)


async def seed_scenarios(session: AsyncSession, users: dict[str, User]) -> None:
    import uuid

    from app.core.deps import EventAccess
    from app.modules.activation import service as activation
    from app.modules.campaigns import service as campaigns
    from app.modules.campaigns.models import Campaign, CampaignQR, CampaignStatus
    from app.modules.campaigns.schemas import CampaignCreate
    from app.modules.checkin import service as checkin
    from app.modules.checkin.models import CheckInRecord
    from app.modules.checkin.schemas import ScanIn
    from app.modules.events import service as events
    from app.modules.events.models import Event, EventStatus
    from app.modules.events.schemas import EventCreate, StaffCreate
    from app.modules.orders import checkout
    from app.modules.orders.models import Order, OrderItem
    from app.modules.orders.schemas import CheckoutCreate, CheckoutItem
    from app.modules.payments import service as payments
    from app.modules.support import service as support
    from app.modules.support.models import SupportCase, SupportMessage
    from app.modules.support.schemas import CaseCreate, MessageCreate
    from app.modules.ticketing import service as inventory
    from app.modules.ticketing.models import TicketType
    from app.modules.ticketing.schemas import TicketTypeCreate
    from app.modules.tickets.models import Ticket, TicketStatus
    from app.modules.users.models import StaffAssignment, StaffRole

    owner, buyer, scanner = (
        users[email]
        for email in (ORGANIZER_EMAIL, "attendee@example.com", "eventadmin@example.com")
    )
    for offset, (title, price) in enumerate(
        (("Almaty Live Demo", 4500), ("Community Workshop Demo", 0))
    ):
        event = await session.scalar(
            select(Event).where(
                Event.title == title,
                Event.organizer_profile_id
                == (
                    select(OrganizerProfile.id)
                    .where(OrganizerProfile.user_id == owner.id)
                    .scalar_subquery()
                ),
            )
        )
        if event is None:
            start = (datetime.now(UTC) + timedelta(days=14 + offset)).replace(
                hour=13, minute=0, second=0, microsecond=0
            )
            event = await events.create(
                session,
                owner,
                EventCreate(
                    title=title,
                    description="A live demo event in Almaty. All payments are simulated.",
                    starts_at=start,
                    ends_at=start + timedelta(hours=3),
                    capacity=100,
                    venue_id=uuid.UUID("20000000-0000-0000-0000-000000000001"),
                ),
            )
        # A seed rerun must not reverse a teammate's moderation or cancellation.
        if (
            event.status == EventStatus.CANCELLED
            or event.is_suspended
            or event.paid_sales_status == "suspended"
        ):
            continue
        access = EventAccess(owner, event.id, True, frozenset(), False)
        ticket_type = await session.scalar(
            select(TicketType)
            .where(TicketType.event_id == event.id)
            .order_by(TicketType.created_at)
            .limit(1)
        )
        if ticket_type is None:
            ticket_type = await inventory.save(
                session,
                access,
                TicketTypeCreate(name="General admission", quantity_total=100, price_amount=price),
            )
        assigned = await session.scalar(
            select(StaffAssignment.id).where(
                StaffAssignment.event_id == event.id,
                StaffAssignment.user_id == scanner.id,
            )
        )
        if assigned is None and event.status != EventStatus.CANCELLED:
            await events.add_staff(
                session, access, StaffCreate(email=scanner.email, role=StaffRole.EVENT_ADMIN)
            )
        campaign = None
        if price:
            campaign = await session.scalar(select(Campaign).where(Campaign.event_id == event.id))
            if campaign is None:
                created = await campaigns.create(
                    session,
                    access,
                    CampaignCreate(
                        name="Demo launch",
                        discount_type="percent",
                        discount_value=15,
                        code="DEMO15",
                    ),
                )
                campaign = await session.get(Campaign, created.id)
            if campaign.status == CampaignStatus.DRAFT:
                await campaigns.transition(session, access, campaign.id, CampaignStatus.ACTIVE)
            if not await session.scalar(
                select(CampaignQR.id).where(CampaignQR.campaign_id == campaign.id)
            ):
                await campaigns.create_qr(session, access, campaign.id, None)
            checklist = await activation.checklist(session, event)
            if (
                checklist.paid_sales_status != "active"
                and event.status != EventStatus.CANCELLED
                and not event.is_suspended
            ):
                await activation.accept_terms(session, event.id, owner)
                payment = await activation.pay(session, event.id, owner)
                if payment.status == "initiated":
                    await activation.simulate(session, owner, payment.id, "success")
                await activation.activate(session, event.id, owner)
        if event.status == EventStatus.DRAFT:
            await events.transition(session, access, EventStatus.PUBLISHED)
        order = await session.scalar(
            select(Order)
            .where(Order.event_id == event.id, Order.buyer_user_id == buyer.id)
            .order_by(Order.created_at)
            .limit(1)
        )
        if order is None and event.status == EventStatus.PUBLISHED:
            result = await checkout.create(
                session,
                event.id,
                buyer,
                CheckoutCreate(
                    items=[CheckoutItem(ticket_type_id=ticket_type.id, quantity=2)],
                    promo_code="DEMO15" if price else None,
                ),
            )
            order = await session.get(Order, result.id)
            if price:
                payment = await payments.pay(session, buyer, order.id)
                await payments.simulate(session, buyer, payment.id, "success")
        if order is None:
            continue
        ticket = await session.scalar(
            select(Ticket)
            .join(OrderItem, Ticket.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order.id)
            .order_by(Ticket.id)
            .limit(1)
        )
        if (
            ticket
            and ticket.status == TicketStatus.VALID
            and not await session.scalar(
                select(CheckInRecord.id).where(CheckInRecord.ticket_id == ticket.id)
            )
        ):
            await checkin.scan(
                session,
                EventAccess(scanner, event.id, False, frozenset({StaffRole.EVENT_ADMIN}), False),
                ScanIn(token=ticket.qr_token),
            )
        case = await session.scalar(select(SupportCase).where(SupportCase.order_id == order.id))
        if case is None:
            result = await support.create(
                session,
                buyer,
                CaseCreate(
                    order_id=order.id,
                    category="ticket_delivery",
                    subject="Where is my printable ticket?",
                    body="Can I bring my ticket as a PDF?",
                ),
            )
            case = await session.get(SupportCase, result.id)
        if (
            await session.scalar(
                select(SupportMessage.id).where(
                    SupportMessage.case_id == case.id, SupportMessage.sender_user_id == owner.id
                )
            )
            is None
        ):
            await support.post_message(
                session,
                await support.access_case(session, owner, case.id),
                MessageCreate(
                    body="Yes. Open My tickets and download your A4 ticket. We can scan the same QR from your phone."
                ),
            )
    await session.commit()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed(session)
    await engine.dispose()
    print(f"Demo accounts (password for all: {DEMO_PASSWORD}):")
    for account in DEMO_ACCOUNTS:
        print(f"  {account.email:<26} {account.role}")


if __name__ == "__main__":
    asyncio.run(main())
