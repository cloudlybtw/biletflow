import secrets
import uuid
from datetime import UTC, datetime

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import EventAccess
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, AppError
from app.core.pagination import Pagination
from app.modules.campaigns.discounts import DiscountLine, calculate_discount
from app.modules.campaigns.models import (
    Campaign,
    CampaignQR,
    CampaignStatus,
    CampaignTicketType,
    PromoCode,
)
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignFields,
    CampaignOut,
    CampaignUpdate,
    CodeOut,
    DiscountPreview,
    LinkOut,
    PromoValidate,
)
from app.modules.events.models import Event, EventStatus, EventVisibility
from app.modules.events.service import audit, editable, get_event
from app.modules.ticketing.models import TicketType

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


async def get_campaign(
    session: AsyncSession, event_id: uuid.UUID, campaign_id: uuid.UUID, *, lock=False
) -> Campaign:
    query = select(Campaign).where(Campaign.id == campaign_id, Campaign.event_id == event_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    campaign = await session.scalar(query)
    if campaign is None:
        raise AppError(NOT_FOUND, "Campaign not found.", 404)
    return campaign


async def campaign_outputs(session: AsyncSession, campaigns: list[Campaign]) -> list[CampaignOut]:
    ids = [campaign.id for campaign in campaigns]
    mappings = (
        await session.execute(
            select(CampaignTicketType.campaign_id, CampaignTicketType.ticket_type_id)
            .where(CampaignTicketType.campaign_id.in_(ids))
            .order_by(CampaignTicketType.ticket_type_id)
        )
    ).all()
    codes = (
        await session.scalars(
            select(PromoCode)
            .where(PromoCode.campaign_id.in_(ids))
            .order_by(PromoCode.created_at, PromoCode.id)
        )
    ).all()
    return [
        CampaignOut.model_validate(campaign).model_copy(
            update={
                "ticket_type_ids": [
                    ticket_id for campaign_id, ticket_id in mappings if campaign_id == campaign.id
                ],
                "promo_codes": [
                    CodeOut.model_validate(code)
                    for code in codes
                    if code.campaign_id == campaign.id
                ],
            }
        )
        for campaign in campaigns
    ]


async def output(session: AsyncSession, campaign: Campaign) -> CampaignOut:
    return (await campaign_outputs(session, [campaign]))[0]


async def list_campaigns(
    session: AsyncSession, event_id: uuid.UUID, page: Pagination
) -> tuple[list[CampaignOut], int]:
    total = await session.scalar(
        select(func.count()).select_from(Campaign).where(Campaign.event_id == event_id)
    )
    campaigns = list(
        (
            await session.scalars(
                select(Campaign)
                .where(Campaign.event_id == event_id)
                .order_by(Campaign.created_at, Campaign.id)
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return await campaign_outputs(session, campaigns), total or 0


async def validate_types(session: AsyncSession, event_id: uuid.UUID, ids: list[uuid.UUID]):
    if not ids:
        return
    actual = set(
        (
            await session.scalars(
                select(TicketType.id).where(TicketType.event_id == event_id, TicketType.id.in_(ids))
            )
        ).all()
    )
    if actual != set(ids):
        raise AppError(
            VALIDATION_ERROR, "Every applicable ticket type must belong to this event.", 422
        )


async def insert_code(session: AsyncSession, campaign: Campaign, custom: str | None) -> PromoCode:
    for _ in range(5):
        code = PromoCode(
            campaign_id=campaign.id,
            code=custom or "BF-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(10)),
        )
        try:
            async with session.begin_nested():
                session.add(code)
                await session.flush()
            return code
        except IntegrityError as exc:
            if custom:
                raise AppError(
                    "PROMO_CODE_TAKEN", "This promo code is already in use.", 409
                ) from exc
    raise AppError(
        "PROMO_CODE_UNAVAILABLE", "Could not allocate a unique promo code. Try again.", 503
    )


async def create(session: AsyncSession, access: EventAccess, data: CampaignCreate) -> CampaignOut:
    editable(await get_event(session, access.event_id, lock=True))
    await validate_types(session, access.event_id, data.ticket_type_ids)
    campaign = Campaign(
        event_id=access.event_id,
        created_by=access.user.id,
        **data.model_dump(exclude={"code", "ticket_type_ids"}),
    )
    session.add(campaign)
    await session.flush()
    session.add_all(
        [
            CampaignTicketType(campaign_id=campaign.id, ticket_type_id=t)
            for t in data.ticket_type_ids
        ]
    )
    code = await insert_code(session, campaign, data.code)
    await audit(
        session,
        access,
        "campaign.created",
        campaign,
        {"fields": data.model_dump(exclude={"code"}), "promo_code": code.code},
    )
    await session.commit()
    return await output(session, campaign)


async def edit(
    session: AsyncSession, access: EventAccess, campaign_id: uuid.UUID, data: CampaignUpdate
) -> CampaignOut:
    editable(await get_event(session, access.event_id, lock=True))
    campaign = await get_campaign(session, access.event_id, campaign_id, lock=True)
    if campaign.status in {CampaignStatus.DISABLED, CampaignStatus.EXPIRED}:
        raise AppError("CAMPAIGN_DISABLED", "Disabled/expired campaigns cannot be edited.", 409)
    current = await output(session, campaign)
    changes = data.model_dump(exclude_unset=True)
    try:
        merged = CampaignFields.model_validate(
            {**{key: getattr(current, key) for key in CampaignFields.model_fields}, **changes}
        )
    except ValidationError as exc:
        raise AppError(
            VALIDATION_ERROR,
            "Invalid campaign fields.",
            422,
            {"errors": jsonable_encoder(exc.errors())},
        ) from exc
    if merged.max_redemptions is not None and merged.max_redemptions < campaign.redemption_count:
        raise AppError(
            "LIMIT_BELOW_REDEMPTIONS", "Limit cannot fall below existing redemptions.", 409
        )
    await validate_types(session, access.event_id, merged.ticket_type_ids)
    before = {key: getattr(current, key) for key in changes}
    for key, value in merged.model_dump(exclude={"ticket_type_ids"}).items():
        setattr(campaign, key, value)
    if "ticket_type_ids" in changes:
        await session.execute(
            delete(CampaignTicketType).where(CampaignTicketType.campaign_id == campaign.id)
        )
        session.add_all(
            [
                CampaignTicketType(campaign_id=campaign.id, ticket_type_id=t)
                for t in merged.ticket_type_ids
            ]
        )
    await audit(session, access, "campaign.updated", campaign, {"before": before, "after": changes})
    await session.commit()
    return await output(session, campaign)


async def transition(
    session: AsyncSession, access: EventAccess, campaign_id: uuid.UUID, target: CampaignStatus
) -> CampaignOut:
    editable(await get_event(session, access.event_id, lock=True))
    campaign = await get_campaign(session, access.event_id, campaign_id, lock=True)
    if (campaign.status, target) not in {
        (CampaignStatus.DRAFT, CampaignStatus.ACTIVE),
        (CampaignStatus.ACTIVE, CampaignStatus.DISABLED),
    }:
        raise AppError(
            "INVALID_CAMPAIGN_TRANSITION", "Only draft → active → disabled is allowed.", 409
        )
    if (
        target == CampaignStatus.ACTIVE
        and campaign.ends_at
        and campaign.ends_at <= datetime.now(UTC)
    ):
        raise AppError("PROMO_EXPIRED", "This campaign has already ended.", 409)
    campaign.status = target
    await audit(session, access, f"campaign.{target.value}", campaign)
    await session.commit()
    return await output(session, campaign)


async def delete_campaign(session: AsyncSession, access: EventAccess, campaign_id: uuid.UUID):
    editable(await get_event(session, access.event_id, lock=True))
    campaign = await get_campaign(session, access.event_id, campaign_id, lock=True)
    if campaign.status != CampaignStatus.DRAFT or campaign.redemption_count:
        raise AppError(
            "CAMPAIGN_NOT_DRAFT",
            "Only unused draft campaigns can be deleted; disable active campaigns.",
            409,
        )
    await audit(session, access, "campaign.deleted", campaign)
    try:
        await session.delete(campaign)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            "CAMPAIGN_IN_USE",
            "This campaign is referenced by purchases and cannot be deleted.",
            409,
        ) from exc


async def add_code(
    session: AsyncSession, access: EventAccess, campaign_id: uuid.UUID, custom: str | None
) -> PromoCode:
    editable(await get_event(session, access.event_id, lock=True))
    campaign = await get_campaign(session, access.event_id, campaign_id, lock=True)
    if campaign.status in {CampaignStatus.DISABLED, CampaignStatus.EXPIRED}:
        raise AppError("CAMPAIGN_DISABLED", "Cannot add codes to a disabled/expired campaign.", 409)
    code = await insert_code(session, campaign, custom)
    await audit(
        session, access, "promo_code.created", code, {"code": code.code, "campaign_id": campaign.id}
    )
    await session.commit()
    return code


async def create_qr(
    session: AsyncSession,
    access: EventAccess,
    campaign_id: uuid.UUID,
    promo_code_id: uuid.UUID | None,
) -> CampaignQR:
    editable(await get_event(session, access.event_id, lock=True))
    campaign = await get_campaign(session, access.event_id, campaign_id, lock=True)
    if campaign.status in {CampaignStatus.DISABLED, CampaignStatus.EXPIRED}:
        raise AppError(
            "CAMPAIGN_DISABLED", "Cannot create QR codes for a disabled/expired campaign.", 409
        )
    query = select(PromoCode).where(PromoCode.campaign_id == campaign.id, PromoCode.is_active)
    if promo_code_id:
        query = query.where(PromoCode.id == promo_code_id)
    code = await session.scalar(query.order_by(PromoCode.created_at, PromoCode.id).limit(1))
    if code is None:
        raise AppError(NOT_FOUND, "Active promo code not found in this campaign.", 404)
    token = "bfc_" + secrets.token_urlsafe(24)
    qr = CampaignQR(
        campaign_id=campaign.id,
        promo_code_id=code.id,
        token=token,
        target_url=f"{get_settings().web_base_url.rstrip('/')}/campaign-links/{token}",
        label="PROMO",
        image_url=f"/api/v1/events/{access.event_id}/campaigns/{campaign.id}/qr/{token}.png",
    )
    session.add(qr)
    await session.flush()
    await audit(
        session,
        access,
        "campaign_qr.created",
        qr,
        {"campaign_id": campaign.id, "promo_code_id": code.id},
    )
    await session.commit()
    return qr


def ensure_usable(campaign: Campaign, code: PromoCode, now: datetime) -> None:
    if not code.is_active or campaign.status in {CampaignStatus.DRAFT, CampaignStatus.DISABLED}:
        raise AppError("PROMO_DISABLED", "This promo is not active.")
    if campaign.status == CampaignStatus.EXPIRED or (campaign.ends_at and campaign.ends_at <= now):
        raise AppError("PROMO_EXPIRED", "This promo has expired.")
    if campaign.starts_at and campaign.starts_at > now:
        raise AppError("PROMO_NOT_STARTED", "This promo is not available yet.")
    if (
        campaign.max_redemptions is not None
        and campaign.redemption_count >= campaign.max_redemptions
    ):
        raise AppError("PROMO_EXHAUSTED", "This promo has reached its redemption limit.")


async def public_event(session: AsyncSession, event_id: uuid.UUID) -> Event:
    event = await get_event(session, event_id)
    if (
        event.is_suspended
        or event.status != EventStatus.PUBLISHED
        or event.visibility == EventVisibility.PRIVATE
    ):
        raise AppError(NOT_FOUND, "Event not found.", 404)
    return event


async def resolve_link(session: AsyncSession, token: str) -> LinkOut:
    if not token.startswith("bfc_") or len(token) > 100:
        raise AppError(NOT_FOUND, "Campaign link not found.", 404)
    row = (
        await session.execute(
            select(CampaignQR, Campaign, PromoCode, Event)
            .join(Campaign, Campaign.id == CampaignQR.campaign_id)
            .join(PromoCode, PromoCode.id == CampaignQR.promo_code_id)
            .join(Event, Event.id == Campaign.event_id)
            .where(
                CampaignQR.token == token,
                Event.deleted_at.is_(None),
                ~Event.is_suspended,
                Event.status == EventStatus.PUBLISHED,
                Event.visibility != EventVisibility.PRIVATE,
            )
        )
    ).one_or_none()
    if row is None:
        raise AppError(NOT_FOUND, "Campaign link not found.", 404)
    qr, campaign, code, event = row
    ensure_usable(campaign, code, datetime.now(UTC))
    await session.execute(
        update(CampaignQR)
        .where(CampaignQR.id == qr.id)
        .values(scan_count=CampaignQR.scan_count + 1)
    )
    result = LinkOut(event_slug=event.slug, promo_code=code.code, campaign_id=campaign.id)
    await session.commit()
    return result


async def preview(
    session: AsyncSession, event_id: uuid.UUID, data: PromoValidate
) -> DiscountPreview:
    await public_event(session, event_id)
    row = (
        await session.execute(
            select(Campaign, PromoCode)
            .join(PromoCode, PromoCode.campaign_id == Campaign.id)
            .where(Campaign.event_id == event_id, PromoCode.code == data.code)
        )
    ).one_or_none()
    if row is None:
        raise AppError("PROMO_NOT_APPLICABLE", "Promo code does not apply to this event.")
    campaign, code = row
    ensure_usable(campaign, code, datetime.now(UTC))
    quantities = {item.ticket_type_id: item.quantity for item in data.items}
    types = list(
        (
            await session.scalars(
                select(TicketType).where(
                    TicketType.event_id == event_id,
                    TicketType.id.in_(quantities),
                    ~TicketType.is_hidden,
                )
            )
        ).all()
    )
    if len(types) != len(quantities):
        raise AppError("PROMO_NOT_APPLICABLE", "Cart contains an unavailable ticket type.")
    if any(
        not ticket.min_per_order <= quantities[ticket.id] <= ticket.max_per_order
        for ticket in types
    ):
        raise AppError("INVALID_CART", "Cart quantities do not meet per-order limits.")
    applicable = set(
        (
            await session.scalars(
                select(CampaignTicketType.ticket_type_id).where(
                    CampaignTicketType.campaign_id == campaign.id
                )
            )
        ).all()
    )
    amounts = calculate_discount(
        campaign.discount_type,
        campaign.discount_value,
        [DiscountLine(ticket.id, ticket.price_amount, quantities[ticket.id]) for ticket in types],
        applicable,
    )
    if amounts.eligible_subtotal_amount == 0:
        raise AppError("PROMO_NOT_APPLICABLE", "No eligible paid tickets in this cart.")
    return DiscountPreview(
        campaign_id=campaign.id,
        promo_code_id=code.id,
        subtotal_amount=amounts.subtotal_amount,
        eligible_subtotal_amount=amounts.eligible_subtotal_amount,
        discount_amount=amounts.discount_amount,
        total_amount=amounts.total_amount,
    )
