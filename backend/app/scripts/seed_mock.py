"""Bulk mock data for UI work: `uv run python -m app.scripts.seed_mock`.

Builds on `seed_demo` (run first for the base accounts). Adds extra organizers,
attendees, events across every category, ticket types, simulated orders and a
few check-ins, all through the same services the API uses. Idempotent: users
are matched by email and events by (organizer, title). Never run it against a
database with real users.
"""

import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.models  # noqa: F401  (registers every mapper)
from app.core.deps import EventAccess
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.modules.activation import service as activation
from app.modules.events import service as events
from app.modules.events.models import Event, EventStatus
from app.modules.events.schemas import EventCreate, StaffCreate
from app.modules.orders import checkout
from app.modules.orders.models import Order
from app.modules.orders.schemas import CheckoutCreate, CheckoutItem
from app.modules.organizers.models import (
    OrganizerProfile,
    PayoutAccount,
    PayoutAccountStatus,
    VerificationStatus,
)
from app.modules.organizers.service import SIMULATED_PAYOUT_PROVIDER
from app.modules.payments import service as payments
from app.modules.ticketing import service as inventory
from app.modules.ticketing.models import TicketType
from app.modules.ticketing.schemas import TicketTypeCreate
from app.modules.users.models import StaffRole, User
from app.scripts.seed_demo import DEMO_PASSWORD, seed

CATEGORY_IDS = {
    "music": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "theatre": uuid.UUID("10000000-0000-0000-0000-000000000002"),
    "sports": uuid.UUID("10000000-0000-0000-0000-000000000003"),
    "education": uuid.UUID("10000000-0000-0000-0000-000000000004"),
}
DEMO_VENUE = uuid.UUID("20000000-0000-0000-0000-000000000001")
SCANNER_EMAIL = "eventadmin@example.com"

ORGANIZERS = (
    ("astana.concerts@example.com", "Aigerim Concerts", "Astana Concerts"),
    ("steppe.sports@example.com", "Bauyrzhan Sports", "Steppe Sports Club"),
    ("nu.learning@example.com", "Dina Learning", "Qazaq Learning Hub"),
)
ATTENDEES = (
    "Aidos Nurlan",
    "Madina Sagyn",
    "Yerlan Abay",
    "Zarina Kenes",
    "Timur Omar",
    "Aruzhan Bek",
    "Nursultan Dos",
    "Kamila Yess",
    "Dias Serik",
    "Assel Tolegen",
    "Ruslan Amir",
    "Laura Zhan",
)

# (organizer index, title, category, days ahead, price in tenge, capacity, has VIP tier)
EVENTS = (
    (0, "Jazz Night at the Opera", "music", 6, 8000, 300, True),
    (0, "Indie Showcase Almaty", "music", 12, 5000, 200, False),
    (0, "Open Air Folk Festival", "music", 30, 0, 800, False),
    (0, "Classical Evenings: Beethoven", "music", 21, 12000, 150, True),
    (1, "Almaty Marathon 10K", "sports", 18, 3000, 500, False),
    (1, "Charity Football Match", "sports", 9, 2000, 400, False),
    (1, "Chess Open Championship", "sports", 25, 0, 120, False),
    (1, "Yoga in the Park", "sports", 4, 1500, 60, False),
    (2, "Intro to Python Workshop", "education", 7, 0, 40, False),
    (2, "Startup Pitch Day", "education", 15, 4000, 100, True),
    (2, "Data Science Bootcamp", "education", 28, 15000, 50, False),
    (2, "Kazakh Literature Reading", "theatre", 10, 2500, 80, False),
    (0, "The Cherry Orchard (Drama)", "theatre", 14, 6000, 250, True),
    (1, "Stand-up Comedy Night", "theatre", 5, 4500, 180, False),
)
# Left as drafts so organizer dashboards show every status.
DRAFT_TITLES = {"Data Science Bootcamp", "Open Air Folk Festival"}


async def ensure_user(session: AsyncSession, email: str, name: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name=name,
            locale=random.choice(("ru", "kk", "en")),
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
    return user


async def ensure_organizer(session: AsyncSession, user: User, display_name: str) -> None:
    profile = await session.scalar(
        select(OrganizerProfile).where(OrganizerProfile.user_id == user.id)
    )
    if profile is None:
        profile = OrganizerProfile(
            user_id=user.id,
            display_name=display_name,
            contact_email=user.email,
            contact_phone="+77010000000",
            description=f"{display_name}: mock organizer for BiletFlow.",
            verification_status=VerificationStatus.VERIFIED,
            verified_at=datetime.now(UTC),
        )
        session.add(profile)
        await session.flush()
    if not await session.scalar(
        select(PayoutAccount.id).where(PayoutAccount.organizer_profile_id == profile.id)
    ):
        session.add(
            PayoutAccount(
                organizer_profile_id=profile.id,
                provider=SIMULATED_PAYOUT_PROVIDER,
                external_account_ref=f"KZ00MOCK{abs(hash(user.email)) % 10**12:012d}",
                account_holder_name=user.full_name,
                status=PayoutAccountStatus.ACTIVE,
                is_default=True,
                is_simulated=True,
            )
        )
    await session.commit()


async def seed_event(
    session: AsyncSession,
    owner: User,
    spec: tuple,
    scanner: User,
) -> Event | None:
    _, title, category, days, price, capacity, has_vip = spec
    profile_id = (
        select(OrganizerProfile.id).where(OrganizerProfile.user_id == owner.id).scalar_subquery()
    )
    event = await session.scalar(
        select(Event).where(Event.title == title, Event.organizer_profile_id == profile_id)
    )
    if event is not None:
        return event
    start = (datetime.now(UTC) + timedelta(days=days)).replace(
        hour=random.choice((12, 14, 16, 18)), minute=0, second=0, microsecond=0
    )
    event = await events.create(
        session,
        owner,
        EventCreate(
            title=title,
            description=f"{title}: mock event for UI development. All payments are simulated.",
            starts_at=start,
            ends_at=start + timedelta(hours=random.choice((2, 3, 4))),
            capacity=capacity,
            venue_id=DEMO_VENUE,
            category_id=CATEGORY_IDS[category],
        ),
    )
    access = EventAccess(owner, event.id, True, frozenset(), False)
    tiers = [("General admission", price, capacity - (capacity // 5 if has_vip else 0))]
    if has_vip:
        tiers.append(("VIP", price * 2, capacity // 5))
    for order_, (name, tier_price, qty) in enumerate(tiers):
        await inventory.save(
            session,
            access,
            TicketTypeCreate(
                name=name, quantity_total=qty, price_amount=tier_price, display_order=order_
            ),
        )
    await events.add_staff(
        session, access, StaffCreate(email=scanner.email, role=StaffRole.EVENT_ADMIN)
    )
    if title in DRAFT_TITLES:
        return event
    if price:
        await activation.accept_terms(session, event.id, owner)
        payment = await activation.pay(session, event.id, owner)
        if payment.status == "initiated":
            await activation.simulate(session, owner, payment.id, "success")
        await activation.activate(session, event.id, owner)
    await events.transition(session, access, EventStatus.PUBLISHED)
    return event


async def seed_orders(session: AsyncSession, event: Event, buyers: list[User]) -> int:
    if event.status != EventStatus.PUBLISHED:
        return 0
    if await session.scalar(select(Order.id).where(Order.event_id == event.id).limit(1)):
        return 0
    types = list(await session.scalars(select(TicketType).where(TicketType.event_id == event.id)))
    placed = 0
    for buyer in random.sample(buyers, k=random.randint(3, min(8, len(buyers)))):
        ticket_type = random.choice(types)
        try:
            result = await checkout.create(
                session,
                event.id,
                buyer,
                CheckoutCreate(
                    items=[
                        CheckoutItem(ticket_type_id=ticket_type.id, quantity=random.randint(1, 4))
                    ]
                ),
            )
            if ticket_type.price_amount:
                payment = await payments.pay(session, buyer, result.id)
                # Mostly successes, with an occasional failure for realistic admin views.
                outcome = "success" if random.random() < 0.9 else "failure"
                await payments.simulate(session, buyer, payment.id, outcome)
            placed += 1
        except AppError as exc:
            print(f"  skipped an order for {event.title!r}: {exc.code}")
            await session.rollback()
    return placed


async def main() -> None:
    random.seed(361)
    async with AsyncSessionLocal() as session:
        await seed(session)  # base demo accounts, venue events, scanner
        owners = []
        for email, name, display in ORGANIZERS:
            user = await ensure_user(session, email, name)
            await ensure_organizer(session, user, display)
            owners.append(user)
        buyers = [
            await ensure_user(
                session, f"{n.split()[0].lower()}.{n.split()[1].lower()}@example.com", n
            )
            for n in ATTENDEES
        ]
        await session.commit()
        scanner = await session.scalar(select(User).where(User.email == SCANNER_EMAIL))
        total_orders = 0
        for spec in EVENTS:
            event = await seed_event(session, owners[spec[0]], spec, scanner)
            total_orders += await seed_orders(session, event, buyers)
        await session.commit()
    await engine.dispose()
    print(f"\nMock data ready: {len(EVENTS)} events, {total_orders} new orders.")
    print(f"Password for every account: {DEMO_PASSWORD}")
    for email, _, display in ORGANIZERS:
        print(f"  organizer  {email:<32} {display}")
    print(f"  attendees  {len(ATTENDEES)} accounts, e.g. aidos.nurlan@example.com")


if __name__ == "__main__":
    asyncio.run(main())
