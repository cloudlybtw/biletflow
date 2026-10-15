import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, require_verified
from app.core.pagination import Page, Pagination, pagination
from app.db.session import get_session
from app.modules.orders import checkout, service
from app.modules.orders.schemas import CheckoutCreate, OrderDetail, OrderOut
from app.modules.payments import service as payments
from app.modules.payments.schemas import PaymentOut
from app.modules.users.models import User

router = APIRouter(tags=["orders"])


@router.post(
    "/events/{event_id}/orders",
    response_model=OrderDetail,
    status_code=201,
    summary="Reserve a cart or complete a free order",
    description="Requires a verified account. Uses current prices and platform fees; atomically holds inventory and any positive promo discount. Zero-total orders complete immediately and issue tickets.",
)
async def create_order(
    event_id: uuid.UUID,
    data: CheckoutCreate,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    return await checkout.create(session, event_id, user, data)


@router.get("/orders", response_model=Page[OrderOut], summary="My orders")
async def my_orders(
    page: Pagination = Depends(pagination),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.my_orders(session, user, page)
    return Page(items=items, total=total)


@router.get(
    "/orders/{order_id}",
    response_model=OrderDetail,
    summary="My order detail (lazily expires stale reservations)",
)
async def order_detail(
    order_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.detail(session, user, order_id)


@router.post(
    "/orders/{order_id}/pay",
    response_model=PaymentOut,
    status_code=201,
    summary="Start or reuse a simulated payment attempt",
)
async def pay(
    order_id: uuid.UUID,
    user: User = Depends(require_verified),
    session: AsyncSession = Depends(get_session),
):
    return await payments.pay(session, user, order_id)
