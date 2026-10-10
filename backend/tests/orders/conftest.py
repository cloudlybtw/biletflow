from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.campaigns.models import Campaign, CampaignStatus, DiscountType, PromoCode
from app.modules.events.models import EventStatus, PaidSalesStatus
from tests.factories import create_event, create_organizer, create_ticket_type, create_verified_user


@pytest.fixture
async def context(db_session):
    buyer = await create_verified_user(db_session)
    other_buyer = await create_verified_user(db_session)
    profile = await create_organizer(db_session)
    event_id = await create_event(
        db_session, profile, status=EventStatus.PUBLISHED, paid_sales_status=PaidSalesStatus.ACTIVE
    )
    ticket_type = await create_ticket_type(
        db_session, event_id, price_amount=1000, quantity_total=100
    )
    await db_session.commit()
    return SimpleNamespace(
        buyer=buyer, other_buyer=other_buyer, event_id=event_id, ticket_type=ticket_type
    )


async def add_promo(
    db_session, context, *, value=15, kind=DiscountType.PERCENT, maximum=None, types=()
):
    campaign = Campaign(
        event_id=context.event_id,
        name="Checkout promo",
        discount_type=kind,
        discount_value=value,
        max_redemptions=maximum,
        status=CampaignStatus.ACTIVE,
        starts_at=datetime.now(UTC) - timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(campaign)
    await db_session.flush()
    code = PromoCode(campaign_id=campaign.id, code="CHECKOUT15")
    db_session.add(code)
    if types:
        from app.modules.campaigns.models import CampaignTicketType

        db_session.add_all(
            [CampaignTicketType(campaign_id=campaign.id, ticket_type_id=t) for t in types]
        )
    await db_session.commit()
    return campaign, code
