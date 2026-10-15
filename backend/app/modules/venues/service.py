import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NOT_FOUND, AppError
from app.core.pagination import Pagination
from app.db.pagination import read_page
from app.modules.venues.models import PriceCategory, Seat, Venue, VenueRow, VenueSection
from app.modules.venues.schemas import (
    PriceCategoryOut,
    RowOut,
    SeatOut,
    SectionOut,
    VenueDetail,
    VenueOut,
)


async def list_venues(session: AsyncSession, page: Pagination):
    return await read_page(session, select(Venue).order_by(Venue.name, Venue.id), page)


async def detail(session: AsyncSession, venue_id: uuid.UUID) -> VenueDetail:
    venue = await session.get(Venue, venue_id)
    if venue is None:
        raise AppError(NOT_FOUND, "Venue not found.", 404)
    categories = (
        await session.scalars(
            select(PriceCategory)
            .where(PriceCategory.venue_id == venue_id)
            .order_by(PriceCategory.code)
        )
    ).all()
    sections = (
        await session.scalars(
            select(VenueSection)
            .where(VenueSection.venue_id == venue_id)
            .order_by(VenueSection.display_order, VenueSection.id)
        )
    ).all()
    rows = (
        await session.scalars(
            select(VenueRow)
            .where(VenueRow.section_id.in_([s.id for s in sections]))
            .order_by(VenueRow.display_order, VenueRow.id)
        )
    ).all()
    seats = (
        await session.scalars(
            select(Seat)
            .where(Seat.row_id.in_([r.id for r in rows]))
            .order_by(Seat.position_x, Seat.id)
        )
    ).all()
    return VenueDetail(
        **VenueOut.model_validate(venue).model_dump(),
        price_categories=[PriceCategoryOut.model_validate(c) for c in categories],
        sections=[
            SectionOut(
                id=s.id,
                name=s.name,
                display_order=s.display_order,
                rows=[
                    RowOut(
                        id=r.id,
                        label=r.label,
                        display_order=r.display_order,
                        seats=[SeatOut.model_validate(t) for t in seats if t.row_id == r.id],
                    )
                    for r in rows
                    if r.section_id == s.id
                ],
            )
            for s in sections
        ],
    )
