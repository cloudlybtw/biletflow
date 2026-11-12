from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizers.models import OrganizerProfile, PayoutAccount
from app.modules.users.models import User
from app.scripts.seed_demo import DEMO_ACCOUNTS, DEMO_PASSWORD, seed


async def _count(session: AsyncSession, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_seed_creates_demo_accounts_idempotently(db_session: AsyncSession):
    await seed(db_session)
    await seed(db_session)

    assert await _count(db_session, User) == len(DEMO_ACCOUNTS)
    assert await _count(db_session, OrganizerProfile) == 1
    assert await _count(db_session, PayoutAccount) == 1
    admin = await db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert admin.platform_role == "platform_admin"
    profile = await db_session.scalar(select(OrganizerProfile))
    assert profile.verification_status == "verified"
    account = await db_session.scalar(select(PayoutAccount))
    assert (account.is_default, account.status, account.is_simulated) == (True, "active", True)


async def test_seeded_accounts_can_log_in(client: AsyncClient, db_session: AsyncSession):
    await seed(db_session)

    for account in DEMO_ACCOUNTS:
        response = await client.post(
            "/api/v1/auth/login", json={"email": account.email, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200, account.email
        assert response.json()["user"]["email_verified"] is True


async def test_scenarios_are_complete_and_reruns_do_not_duplicate_history(db_session):
    from app.modules.campaigns.models import Campaign, CampaignQR
    from app.modules.checkin.models import CheckInRecord
    from app.modules.events.models import Event
    from app.modules.orders.models import Order
    from app.modules.support.models import SupportCase, SupportMessage
    from app.modules.tickets.models import Ticket
    from app.modules.users.models import StaffAssignment

    await seed(db_session)
    models = [
        Event,
        Campaign,
        CampaignQR,
        Order,
        Ticket,
        SupportCase,
        SupportMessage,
        StaffAssignment,
        CheckInRecord,
    ]
    first = [await _count(db_session, model) for model in models]
    assert first == [2, 1, 1, 2, 4, 2, 4, 2, 2]
    await seed(db_session)
    assert [await _count(db_session, model) for model in models] == first
    orders = (await db_session.scalars(select(Order))).all()
    assert all(order.status == "completed" for order in orders)
    assert sorted(order.total_amount for order in orders) == [0, 7650]
