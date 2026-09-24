"""Demo accounts for the web and mobile teams: `uv run python -m app.scripts.seed_demo`.

Idempotent: existing rows (matched by email) are left alone, so it's safe to
re-run. Later milestones extend it with events, tickets, campaigns and so on.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

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
    # Assigned to demo events as event_admin once events exist (M2).
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


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed(session)
    await engine.dispose()
    print(f"Demo accounts (password for all: {DEMO_PASSWORD}):")
    for account in DEMO_ACCOUNTS:
        print(f"  {account.email:<26} {account.role}")


if __name__ == "__main__":
    asyncio.run(main())
