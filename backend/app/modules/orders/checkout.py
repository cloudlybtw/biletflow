import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.settings import checkout_settings
from app.modules.campaigns.discounts import DiscountLine, calculate_discount
from app.modules.campaigns.models import Campaign, CampaignStatus, CampaignTicketType, PromoCode
from app.modules.campaigns.service import ensure_usable
from app.modules.events.models import (
    Event,
    EventStatus,
    EventVisibility,
    PaidSalesStatus,
    SeatingMode,
)
from app.modules.events.service import get_event
from app.modules.orders import service
from app.modules.orders.models import Attendee, Order, OrderItem, PromoRedemption
from app.modules.orders.pricing import MAX_AMOUNT, allocate_discount, processing_fee
from app.modules.orders.schemas import AttendeeInput, CheckoutCreate, OrderDetail
from app.modules.ticketing.holds import SeatHold, SeatHoldStatus
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.users.models import User
from app.modules.users.service import get_event_relation
from app.modules.venues.models import Seat, VenueRow, VenueSection


@dataclass
class ReservedLine:
    ticket_type: TicketType
    quantity: int
    attendees: list[AttendeeInput]
    hold: SeatHold | None = None

    @property
    def subtotal(self) -> int:
        return self.ticket_type.price_amount * self.quantity


def ensure_sales_open(event: Event, now) -> None:
    if event.is_suspended:
        raise AppError("EVENT_SUSPENDED", "This event is suspended.", 409)
    if event.deleted_at is not None or event.status != EventStatus.PUBLISHED:
        raise AppError("EVENT_NOT_PUBLISHED", "This event is not accepting orders.", 409)
    if event.ends_at <= now:
        raise AppError("EVENT_ENDED", "This event has ended.", 409)
    if event.registration_opens_at and event.registration_opens_at > now:
        raise AppError("REGISTRATION_NOT_OPEN", "Registration has not opened yet.", 409)
    if event.registration_closes_at and event.registration_closes_at <= now:
        raise AppError("REGISTRATION_CLOSED", "Registration is closed.", 409)


async def create(session: AsyncSession, event_id, user: User, data: CheckoutCreate) -> OrderDetail:
    event = await get_event(session, event_id, lock=True)
    if await service.expire_event_locked(session, event.id, service.now_utc()):
        # Persist cleanup even when the new cart later fails validation, then
        # re-lock/re-read the event before deciding whether this checkout may proceed.
        await session.commit()
        event = await get_event(session, event_id, lock=True)
    now = service.now_utc()
    if event.visibility == EventVisibility.PRIVATE:
        relation = await get_event_relation(session, event.id, user.id)
        if relation is None or not (relation.is_owner or relation.staff_roles):
            raise AppError("NOT_FOUND", "Event not found.", 404)
    ensure_sales_open(event, now)
    hold_minutes, fee_percent = await checkout_settings(session)
    expires_at = now + timedelta(minutes=hold_minutes)
    campaign, code = None, None
    applicable = set()
    if data.promo_code:
        row = (
            await session.execute(
                select(Campaign, PromoCode)
                .join(PromoCode, PromoCode.campaign_id == Campaign.id)
                .where(Campaign.event_id == event.id, PromoCode.code == data.promo_code)
                .with_for_update(of=Campaign)
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if row is None:
            raise AppError("PROMO_NOT_APPLICABLE", "Promo code does not apply to this event.")
        campaign, code = row
        ensure_usable(campaign, code, now)
        applicable = set(
            (
                await session.scalars(
                    select(CampaignTicketType.ticket_type_id).where(
                        CampaignTicketType.campaign_id == campaign.id
                    )
                )
            ).all()
        )
    requested = {item.ticket_type_id: item for item in data.items}
    types = list(
        (
            await session.scalars(
                select(TicketType)
                .where(TicketType.event_id == event.id, TicketType.id.in_(requested))
                .order_by(TicketType.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if len(types) != len(requested):
        raise AppError("TICKET_TYPE_UNAVAILABLE", "Cart contains an unavailable ticket type.")
    for ticket in types:
        item = requested[ticket.id]
        if ticket.is_hidden:
            raise AppError("TICKET_TYPE_UNAVAILABLE", "This ticket type is hidden.")
        if not ticket.min_per_order <= item.quantity <= ticket.max_per_order:
            raise AppError(
                "ORDER_LIMIT_EXCEEDED", "Quantity is outside this ticket type's per-order limits."
            )
        if ticket.sales_start_at and ticket.sales_start_at > now:
            raise AppError("TICKET_SALES_NOT_OPEN", "Ticket sales have not opened yet.", 409)
        if ticket.sales_end_at and ticket.sales_end_at <= now:
            raise AppError("TICKET_SALES_CLOSED", "Ticket sales are closed.", 409)
        if ticket.price_amount > 0 and event.paid_sales_status != PaidSalesStatus.ACTIVE:
            raise AppError(
                "PAID_SALES_INACTIVE", "Paid sales must be active for paid ticket types.", 409
            )
    hold_ids = [hold for item in data.items for hold in item.seat_hold_ids]
    if event.seating_mode == SeatingMode.ASSIGNED and any(
        not item.seat_hold_ids for item in data.items
    ):
        raise AppError(
            "ASSIGNED_SEATS_REQUIRED",
            "Assigned seating requires one owned seat hold per ticket.",
            422,
        )
    if event.seating_mode != SeatingMode.ASSIGNED and hold_ids:
        raise AppError(
            "SEAT_HOLDS_NOT_ALLOWED", "General-admission orders cannot contain seat holds.", 422
        )
    holds = list(
        (
            await session.scalars(
                select(SeatHold)
                .where(SeatHold.id.in_(hold_ids), SeatHold.event_id == event.id)
                .order_by(SeatHold.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if len(holds) != len(hold_ids) or any(
        hold.held_by_user_id != user.id
        or hold.status != SeatHoldStatus.ACTIVE
        or hold.order_id is not None
        or hold.expires_at <= now
        for hold in holds
    ):
        raise AppError(
            "INVALID_SEAT_HOLD",
            "Seat holds must be active, unexpired, unclaimed and owned by the buyer.",
            409,
        )
    by_hold = {hold.id: hold for hold in holds}
    if holds:
        venue_seats = set(
            (
                await session.scalars(
                    select(Seat.id)
                    .join(VenueRow, VenueRow.id == Seat.row_id)
                    .join(VenueSection, VenueSection.id == VenueRow.section_id)
                    .where(
                        Seat.id.in_([hold.seat_id for hold in holds]),
                        VenueSection.venue_id == event.venue_id,
                    )
                )
            ).all()
        )
        if len(venue_seats) != len(holds):
            raise AppError("INVALID_SEAT_HOLD", "Seat holds do not match this event's venue.", 409)
        sold_seat = await session.scalar(
            select(Ticket.id)
            .where(
                Ticket.event_id == event.id,
                Ticket.seat_id.in_(venue_seats),
                Ticket.status.in_([TicketStatus.VALID, TicketStatus.CHECKED_IN]),
            )
            .limit(1)
        )
        if sold_seat:
            raise AppError("SEAT_UNAVAILABLE", "A selected seat has already been sold.", 409)
    lines: list[ReservedLine] = []
    for ticket in types:
        item = requested[ticket.id]
        attendees = item.attendees or [
            AttendeeInput(full_name=user.full_name, email=user.email, phone=user.phone)
            for _ in range(item.quantity)
        ]
        if item.seat_hold_ids:
            for index, hold_id in enumerate(item.seat_hold_ids):
                hold = by_hold[hold_id]
                if hold.ticket_type_id != ticket.id:
                    raise AppError(
                        "INVALID_SEAT_HOLD", "Seat hold ticket type does not match the cart.", 409
                    )
                lines.append(ReservedLine(ticket, 1, [attendees[index]], hold))
        else:
            lines.append(ReservedLine(ticket, item.quantity, attendees))
    subtotal = sum(line.subtotal for line in lines)
    if subtotal > MAX_AMOUNT:
        raise AppError("CART_TOTAL_TOO_LARGE", "Cart subtotal exceeds the supported amount.", 422)
    discount = 0
    if campaign:
        amounts = calculate_discount(
            campaign.discount_type,
            campaign.discount_value,
            [
                DiscountLine(ticket.id, ticket.price_amount, requested[ticket.id].quantity)
                for ticket in types
            ],
            applicable,
        )
        if not amounts.eligible_subtotal_amount:
            raise AppError("PROMO_NOT_APPLICABLE", "No eligible paid tickets in this cart.")
        discount = amounts.discount_amount
        # A floor-rounded zero discount does not consume a redemption.
        if discount:
            claimed = await session.scalar(
                update(Campaign)
                .where(
                    Campaign.id == campaign.id,
                    Campaign.status == CampaignStatus.ACTIVE,
                    or_(
                        Campaign.max_redemptions.is_(None),
                        Campaign.redemption_count < Campaign.max_redemptions,
                    ),
                )
                .values(redemption_count=Campaign.redemption_count + 1)
                .returning(Campaign.id)
            )
            if claimed is None:
                raise AppError(
                    "PROMO_EXHAUSTED", "This promo has reached its redemption limit.", 409
                )
    fee = processing_fee(subtotal - discount, fee_percent)
    order = Order(
        order_number="BF-" + secrets.token_hex(8).upper(),
        event_id=event.id,
        buyer_user_id=user.id,
        buyer_email=user.email,
        buyer_name=user.full_name,
        buyer_phone=user.phone,
        subtotal_amount=subtotal,
        discount_amount=discount,
        fee_amount=fee,
        total_amount=subtotal - discount + fee,
        campaign_id=campaign.id if campaign else None,
        promo_code_id=code.id if code else None,
        placed_at=now,
        expires_at=expires_at,
    )
    session.add(order)
    await session.flush()
    if discount:
        session.add(
            PromoRedemption(
                promo_code_id=code.id,
                campaign_id=campaign.id,
                order_id=order.id,
                user_id=user.id,
                discount_amount=discount,
            )
        )
    allocations = allocate_discount(
        [line.subtotal for line in lines],
        [not applicable or line.ticket_type.id in applicable for line in lines],
        discount,
    )
    for line, line_discount in zip(lines, allocations, strict=True):
        item = OrderItem(
            order_id=order.id,
            ticket_type_id=line.ticket_type.id,
            seat_id=line.hold.seat_id if line.hold else None,
            quantity=line.quantity,
            unit_price_amount=line.ticket_type.price_amount,
            discount_amount=line_discount,
            line_total=line.subtotal - line_discount,
        )
        session.add(item)
        await session.flush()
        for attendee in line.attendees:
            session.add(
                Attendee(
                    order_item_id=item.id,
                    user_id=user.id
                    if attendee.email and str(attendee.email).casefold() == user.email.casefold()
                    else None,
                    full_name=attendee.full_name,
                    email=str(attendee.email) if attendee.email else None,
                    phone=attendee.phone,
                )
            )
        if line.hold:
            line.hold.order_id = order.id
            line.hold.expires_at = expires_at
    for ticket in types:
        quantity = requested[ticket.id].quantity
        reserved = await session.scalar(
            update(TicketType)
            .where(
                TicketType.id == ticket.id,
                TicketType.quantity_reserved + TicketType.quantity_sold + quantity
                <= TicketType.quantity_total,
            )
            .values(quantity_reserved=TicketType.quantity_reserved + quantity)
            .returning(TicketType.id)
        )
        if reserved is None:
            raise AppError("SOLD_OUT", "Not enough tickets remain.", 409)
    await service.audit(session, order, "order.placed")
    if order.total_amount == 0:
        await service.complete_locked(session, event, order)
    await session.commit()
    return await service.detail(session, user, order.id)
