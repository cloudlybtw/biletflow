import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.users.models import User
from app.modules.venues import service
from app.modules.venues.schemas import VenueCreate, VenueDetail, VenueOut

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=Page[VenueOut])
async def list_venues(
    page: Pagination = Depends(pagination), session: AsyncSession = Depends(get_session)
):
    items, total = await service.list_venues(session, page)
    return Page(items=items, total=total)


@router.post("", response_model=VenueOut, status_code=201)
async def create(
    data: VenueCreate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    return await service.create_venue(session, user, data)


@router.get("/{venue_id}", response_model=VenueDetail)
async def detail(venue_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await service.detail(session, venue_id)
