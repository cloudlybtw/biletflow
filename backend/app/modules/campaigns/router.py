import asyncio
import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import EventAccess, require_event_role
from app.core.errors import NOT_FOUND, AppError
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.campaigns import service
from app.modules.campaigns.models import CampaignQR, CampaignStatus
from app.modules.campaigns.qr import promo_png
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    CodeCreate,
    CodeOut,
    DiscountPreview,
    LinkOut,
    PromoValidate,
    QRCreate,
    QROut,
)
from app.modules.users.models import StaffRole

router = APIRouter(tags=["campaigns"])
manager = require_event_role(StaffRole.CO_ORGANIZER)


@router.get("/events/{event_id}/campaigns", response_model=Page[CampaignOut])
async def list_campaigns(
    event_id: uuid.UUID,
    page: Pagination = Depends(pagination),
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    campaigns, total = await service.list_campaigns(session, access.event_id, page)
    return Page(items=campaigns, total=total)


@router.post("/events/{event_id}/campaigns", response_model=CampaignOut, status_code=201)
async def create(
    event_id: uuid.UUID,
    data: CampaignCreate,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.create(session, access, data)


@router.get("/events/{event_id}/campaigns/{campaign_id}", response_model=CampaignOut)
async def detail(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.output(
        session, await service.get_campaign(session, access.event_id, campaign_id)
    )


@router.patch("/events/{event_id}/campaigns/{campaign_id}", response_model=CampaignOut)
async def edit(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.edit(session, access, campaign_id, data)


@router.delete(
    "/events/{event_id}/campaigns/{campaign_id}", status_code=204, response_class=Response
)
async def delete(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_campaign(session, access, campaign_id)
    return Response(status_code=204)


@router.post("/events/{event_id}/campaigns/{campaign_id}/activate", response_model=CampaignOut)
async def activate(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.transition(session, access, campaign_id, CampaignStatus.ACTIVE)


@router.post("/events/{event_id}/campaigns/{campaign_id}/disable", response_model=CampaignOut)
async def disable(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.transition(session, access, campaign_id, CampaignStatus.DISABLED)


@router.post(
    "/events/{event_id}/campaigns/{campaign_id}/promo-codes",
    response_model=CodeOut,
    status_code=201,
)
async def add_code(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    data: CodeCreate,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.add_code(session, access, campaign_id, data.code)


@router.post("/events/{event_id}/campaigns/{campaign_id}/qr", response_model=QROut, status_code=201)
async def create_qr(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    data: QRCreate,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    return await service.create_qr(session, access, campaign_id, data.promo_code_id)


@router.get("/events/{event_id}/campaigns/{campaign_id}/qr", response_model=list[QROut])
async def list_qrs(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    await service.get_campaign(session, access.event_id, campaign_id)
    return (
        await session.scalars(
            select(CampaignQR)
            .where(CampaignQR.campaign_id == campaign_id)
            .order_by(CampaignQR.created_at, CampaignQR.id)
        )
    ).all()


@router.get(
    "/events/{event_id}/campaigns/{campaign_id}/qr/{token}.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Download a labeled promo QR (not a ticket)",
)
async def qr_image(
    event_id: uuid.UUID,
    campaign_id: uuid.UUID,
    token: str,
    access: EventAccess = Depends(manager),
    session: AsyncSession = Depends(get_session),
):
    await service.get_campaign(session, access.event_id, campaign_id)
    qr = await session.scalar(
        select(CampaignQR).where(CampaignQR.campaign_id == campaign_id, CampaignQR.token == token)
    )
    if qr is None:
        raise AppError(NOT_FOUND, "Campaign QR not found.", 404)
    data = await asyncio.to_thread(promo_png, qr.target_url)
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": 'inline; filename="promo.png"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/campaign-links/{token}",
    response_model=LinkOut,
    description="Resolve an active campaign QR for a published public/unlisted event. Atomically counts successful scans.",
)
async def resolve(token: str, session: AsyncSession = Depends(get_session)):
    return await service.resolve_link(session, token)


@router.post(
    "/events/{event_id}/promo/validate",
    response_model=DiscountPreview,
    description="Read-only discount preview in whole KZT. Does not reserve inventory or claim redemptions. Processing fees are calculated at checkout (M4).",
)
async def validate(
    event_id: uuid.UUID, data: PromoValidate, session: AsyncSession = Depends(get_session)
):
    return await service.preview(session, event_id, data)
