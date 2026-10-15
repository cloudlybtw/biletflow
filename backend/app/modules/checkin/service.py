import uuid
from urllib.parse import urlsplit

from sqlalchemy import Text, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.deps import EventAccess
from app.core.errors import CHECKIN_NOT_REVERSIBLE, NOT_FOUND, AppError
from app.core.pagination import Pagination
from app.modules.campaigns.models import CampaignQR
from app.modules.checkin.models import CheckInAction, CheckInRecord, CheckInResult, CheckInSource
from app.modules.checkin.schemas import (
    CheckInOut,
    CheckInTicketOut,
    CountersOut,
    ReverseIn,
    ScanIn,
)
from app.modules.history.service import record as audit_record
from app.modules.orders.models import Attendee
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket, TicketStatus


def ticket_query():
    reversal = aliased(CheckInRecord)
    was_reversed = (
        select(reversal.id)
        .where(
            reversal.ticket_id == CheckInRecord.ticket_id,
            reversal.reverses_record_id == CheckInRecord.id,
        )
        .exists()
    )
    active_record_id = (
        select(CheckInRecord.id)
        .where(
            CheckInRecord.ticket_id == Ticket.id,
            CheckInRecord.action == CheckInAction.CHECK_IN,
            CheckInRecord.result == CheckInResult.VALID,
            ~was_reversed,
        )
        .order_by(CheckInRecord.scanned_at.desc(), CheckInRecord.id)
        .limit(1)
        .correlate(Ticket)
        .scalar_subquery()
    )
    return (
        select(
            Ticket,
            Attendee,
            TicketType.name,
            case((Ticket.status == TicketStatus.CHECKED_IN, active_record_id), else_=None),
        )
        .join(Attendee, Attendee.id == Ticket.attendee_id)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id)
        .execution_options(populate_existing=True)
    )


def ticket_output(row) -> CheckInTicketOut:
    ticket, attendee, type_name, active_record_id = row
    return CheckInTicketOut(
        ticket_id=ticket.id,
        ticket_code=ticket.ticket_code,
        attendee_name=attendee.full_name,
        attendee_email=attendee.email,
        ticket_type_id=ticket.ticket_type_id,
        ticket_type_name=type_name,
        status=ticket.status,
        checked_in_at=ticket.checked_in_at,
        seat_section_label=ticket.seat_section_label,
        seat_row_label=ticket.seat_row_label,
        seat_number_label=ticket.seat_number_label,
        check_in_record_id=active_record_id,
    )


async def append_record(
    session: AsyncSession,
    access: EventAccess,
    *,
    ticket_id: uuid.UUID | None,
    result: CheckInResult,
    source: CheckInSource,
    device_id: str | None,
    token: str | None = None,
    original: CheckInRecord | None = None,
    notes: str | None = None,
) -> CheckInRecord:
    record = CheckInRecord(
        event_id=access.event_id,
        ticket_id=ticket_id,
        scanned_by_user_id=access.user.id,
        device_id=device_id,
        action=CheckInAction.REVERSE if original else CheckInAction.CHECK_IN,
        result=result,
        source=source,
        scanned_token=token,
        reverses_record_id=original.id if original else None,
        notes=notes,
    )
    session.add(record)
    await session.flush()
    if result == CheckInResult.VALID:
        await audit_record(
            session,
            actor_user_id=access.user.id,
            actor_role=access.actor_role,
            event_id=access.event_id,
            action_type="ticket.check_in_reversed" if original else "ticket.checked_in",
            entity_type="ticket",
            entity_id=ticket_id,
            summary="Ticket check-in reversed" if original else "Ticket checked in",
            metadata={"record_id": str(record.id), "source": source.value},
        )
    return record


def output(record: CheckInRecord, ticket: CheckInTicketOut | None) -> CheckInOut:
    return CheckInOut(
        record_id=record.id,
        event_id=record.event_id,
        action=record.action,
        result=record.result,
        source=record.source,
        scanned_at=record.scanned_at,
        reverses_record_id=record.reverses_record_id,
        ticket=ticket,
    )


async def is_campaign_code(session: AsyncSession, token: str) -> bool:
    # Reject URLs before ticket lookup, including legacy campaign tokens/links.
    if token.startswith("bfc_") or token.startswith("//"):
        return True
    try:
        if urlsplit(token).scheme:
            return True
    except ValueError:
        # Malformed URLs still cannot grant admission.
        if "://" in token:
            return True
    return await session.scalar(select(CampaignQR.id).where(CampaignQR.token == token)) is not None


async def scan(session: AsyncSession, access: EventAccess, data: ScanIn) -> CheckInOut:
    source = CheckInSource.QR_SCAN if data.token is not None else CheckInSource.MANUAL_SEARCH
    token = data.token.strip() if data.token is not None else None
    ticket_id = None
    ticket_out = None
    result = CheckInResult.INVALID
    if token is not None and await is_campaign_code(session, token):
        result = CheckInResult.CAMPAIGN_CODE_REJECTED
    else:
        condition = Ticket.qr_token == token if token is not None else Ticket.id == data.ticket_id
        identity = (
            await session.execute(select(Ticket.id, Ticket.event_id).where(condition))
        ).one_or_none()
        if identity is not None:
            ticket_id, event_id = identity
            if event_id != access.event_id:
                result = CheckInResult.WRONG_EVENT
            else:
                # Keep the outcome and response consistent if an undo races a scan.
                await session.execute(
                    select(Ticket.id).where(Ticket.id == ticket_id).with_for_update()
                )
                # The update itself arbitrates scans across separate sessions.
                won = await session.scalar(
                    update(Ticket)
                    .where(Ticket.id == ticket_id, Ticket.status == TicketStatus.VALID)
                    .values(status=TicketStatus.CHECKED_IN, checked_in_at=func.now())
                    .returning(Ticket.id)
                )
                row = (
                    await session.execute(
                        select(Ticket)
                        .where(Ticket.id == ticket_id)
                        .execution_options(populate_existing=True)
                    )
                ).one()
                result = (
                    CheckInResult.VALID
                    if won is not None
                    else {
                        TicketStatus.CHECKED_IN: CheckInResult.DUPLICATE,
                        TicketStatus.CANCELLED: CheckInResult.CANCELLED,
                        TicketStatus.REFUNDED: CheckInResult.REFUNDED,
                    }[row[0].status]
                )
                record = await append_record(
                    session,
                    access,
                    ticket_id=ticket_id,
                    result=result,
                    source=source,
                    device_id=data.device_id,
                    token=data.token,
                )
                row = (await session.execute(ticket_query().where(Ticket.id == ticket_id))).one()
                ticket_out = ticket_output(row)
                await session.commit()
                return output(record, ticket_out)
    record = await append_record(
        session,
        access,
        ticket_id=ticket_id,
        result=result,
        source=source,
        device_id=data.device_id,
        token=data.token,
    )
    await session.commit()
    return output(record, ticket_out)


async def search(
    session: AsyncSession, access: EventAccess, page: Pagination, query: str | None
) -> tuple[list[CheckInTicketOut], int]:
    statement = ticket_query().where(Ticket.event_id == access.event_id)
    if query and query.strip():
        # Treat SQL wildcard characters as literal user input.
        term = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        statement = statement.where(
            or_(
                Attendee.full_name.ilike(pattern, escape="\\"),
                Attendee.email.cast(Text).ilike(pattern, escape="\\"),
                Ticket.ticket_code.ilike(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.execute(
            statement.order_by(Attendee.full_name, Ticket.id).limit(page.limit).offset(page.offset)
        )
    ).all()
    return [ticket_output(row) for row in rows], total or 0


async def reverse(
    session: AsyncSession, access: EventAccess, record_id: uuid.UUID, data: ReverseIn
) -> CheckInOut:
    original = await session.scalar(
        select(CheckInRecord).where(
            CheckInRecord.id == record_id, CheckInRecord.event_id == access.event_id
        )
    )
    if original is None:
        raise AppError(NOT_FOUND, "Check-in record not found.", 404)
    if original.action != CheckInAction.CHECK_IN or original.result != CheckInResult.VALID:
        raise AppError(CHECKIN_NOT_REVERSIBLE, "Only a successful admission can be reversed.", 409)
    # Lock the ticket before checking the reversal link. This serializes reversals
    # with other reversals and with the scan's conditional ticket update.
    ticket = await session.scalar(
        select(Ticket)
        .where(Ticket.id == original.ticket_id, Ticket.event_id == access.event_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    already_reversed = await session.scalar(
        select(CheckInRecord.id).where(CheckInRecord.reverses_record_id == original.id).limit(1)
    )
    if ticket is None or ticket.status != TicketStatus.CHECKED_IN or already_reversed:
        raise AppError(CHECKIN_NOT_REVERSIBLE, "This admission is no longer reversible.", 409)
    changed = await session.scalar(
        update(Ticket)
        .where(Ticket.id == ticket.id, Ticket.status == TicketStatus.CHECKED_IN)
        .values(status=TicketStatus.VALID, checked_in_at=None)
        .returning(Ticket.id)
    )
    if changed is None:
        raise AppError(CHECKIN_NOT_REVERSIBLE, "This admission is no longer reversible.", 409)
    record = await append_record(
        session,
        access,
        ticket_id=ticket.id,
        result=CheckInResult.VALID,
        source=original.source,
        device_id=data.device_id,
        original=original,
        notes=data.notes,
    )
    row = (await session.execute(ticket_query().where(Ticket.id == ticket.id))).one()
    ticket_out = ticket_output(row)
    await session.commit()
    return output(record, ticket_out)


async def counters(session: AsyncSession, access: EventAccess) -> CountersOut:
    registered, checked_in = (
        await session.execute(
            select(
                func.count().filter(
                    Ticket.status.in_([TicketStatus.VALID, TicketStatus.CHECKED_IN])
                ),
                func.count().filter(Ticket.status == TicketStatus.CHECKED_IN),
            ).where(Ticket.event_id == access.event_id)
        )
    ).one()
    return CountersOut(registered=registered, checked_in=checked_in)
