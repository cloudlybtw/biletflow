import asyncio
import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.tickets import service
from app.modules.tickets.pdf import render as render_pdf
from app.modules.tickets.schemas import TicketOut
from app.modules.users.models import User

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get(
    "/{ticket_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Download my print-optimized A4 ticket",
)
async def pdf(
    ticket_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await service.detail(session, user, ticket_id)
    data = await asyncio.to_thread(render_pdf, ticket)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{ticket.ticket_code}.pdf"',
        },
    )


@router.get("", response_model=Page[TicketOut], summary="My purchased tickets")
async def my_tickets(
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.my_tickets(session, user, page)
    return Page(items=items, total=total)


@router.get(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="My ticket with attendee, event and seat details",
)
async def detail(
    ticket_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.detail(session, user, ticket_id)


@router.get(
    "/{ticket_id}/qr.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Download my ticket QR",
)
async def qr(
    ticket_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await service.detail(session, user, ticket_id)
    data = await asyncio.to_thread(service.qr_png, ticket.qr_token)
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="{ticket.ticket_code}.png"',
        },
    )
