import io
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader
from sqlalchemy import select, update

from app.modules.events.models import Event
from app.modules.orders.models import Attendee
from app.modules.ticketing.models import TicketType
from app.modules.tickets.models import Ticket
from app.modules.tickets.pdf import FONT_DIR, render
from app.modules.tickets.service import detail
from app.modules.venues.models import Seat, VenueRow, VenueSection
from tests.factories import auth_headers


async def test_pdf_is_buyer_only_a4_unicode_and_has_no_payment_or_contact_data(
    client, db_session, admission
):
    await db_session.execute(
        update(Event)
        .where(Event.id == admission.event_id)
        .values(
            title="Қазақстан музыка кеші / Музыкальный вечер",
            timezone="Asia/Almaty",
            starts_at=datetime(2026, 11, 1, 13, 30, tzinfo=UTC),
            ends_at=datetime(2026, 11, 1, 16, 0, tzinfo=UTC),
        )
    )
    await db_session.execute(
        update(Attendee)
        .where(Attendee.id == admission.ticket.attendee_id)
        .values(phone="+77771234567")
    )
    await db_session.commit()
    url = f"/api/v1/tickets/{admission.ticket.id}/pdf"
    assert (await client.get(url)).status_code == 401
    for user in [admission.staff, admission.owner]:
        assert (await client.get(url, headers=auth_headers(user))).status_code == 404
    response = await client.get(url, headers=auth_headers(admission.buyer))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="{admission.ticket.ticket_code}.pdf"'
    )
    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) == pytest.approx(595.276, abs=0.01)
    assert float(reader.pages[0].mediabox.height) == pytest.approx(841.89, abs=0.01)
    text = " ".join(reader.pages[0].extract_text().split())
    assert "Қазақстан музыка кеші / Музыкальный вечер" in text
    assert admission.buyer.full_name in text
    assert "01 Nov 2026, 18:30" in text and "Asia/Almaty" in text
    assert admission.ticket.ticket_code in text
    assert "General admission" in text and "Venue to be announced" in text
    for private in [
        admission.buyer.email,
        "+77771234567",
        "KZT",
        "payment",
        "subtotal",
        "discount",
    ]:
        assert private not in text
    ticket = (
        await client.get(
            f"/api/v1/tickets/{admission.ticket.id}", headers=auth_headers(admission.buyer)
        )
    ).json()
    assert ticket["pdf_url"] == url and ticket["qr_token"] == admission.ticket.qr_token


async def test_pdf_preserves_seat_snapshots_and_current_status(client, db_session, admission):
    seat = await db_session.scalar(select(Seat).limit(1))
    venue_id = await db_session.scalar(
        select(VenueSection.venue_id)
        .join(VenueRow, VenueRow.section_id == VenueSection.id)
        .where(VenueRow.id == seat.row_id)
    )
    await db_session.execute(
        update(Ticket)
        .where(Ticket.id == admission.ticket.id)
        .values(
            seat_id=seat.id,
            seat_section_label="Балкон",
            seat_row_label="Б",
            seat_number_label="12",
            status="refunded",
        )
    )
    await db_session.execute(
        update(Event).where(Event.id == admission.event_id).values(venue_id=venue_id)
    )
    await db_session.commit()
    response = await client.get(
        f"/api/v1/tickets/{admission.ticket.id}/pdf", headers=auth_headers(admission.buyer)
    )
    assert response.status_code == 200, response.text
    text = " ".join(PdfReader(io.BytesIO(response.content)).pages[0].extract_text().split())
    assert "Section Балкон / Row Б / Seat 12" in text
    assert "REFUNDED" in text and "Almaty" in text


async def test_pdf_fits_long_text_and_escapes_markup(db_session, admission):
    await db_session.execute(
        update(Event).where(Event.id == admission.event_id).values(title="Ұ" * 200)
    )
    await db_session.execute(
        update(Attendee)
        .where(Attendee.id == admission.ticket.attendee_id)
        .values(full_name="<b>Әлия & Өмірбек</b>")
    )
    await db_session.execute(
        update(TicketType)
        .where(TicketType.id == admission.ticket.ticket_type_id)
        .values(name="Б" * 200)
    )
    await db_session.commit()
    ticket = await detail(db_session, admission.buyer, admission.ticket.id)
    reader = PdfReader(io.BytesIO(render(ticket)))
    assert len(reader.pages) == 1
    text = " ".join(reader.pages[0].extract_text().split())
    assert "<b>Әлия & Өмірбек</b>" in text and ticket.ticket_code in text
    # Verify the shipped font covers every Kazakh Cyrillic letter, including bold text.
    from reportlab.pdfbase.ttfonts import TTFont

    for filename in ["NotoSans-Regular.ttf", "NotoSans-Bold.ttf"]:
        face = TTFont("coverage", str(FONT_DIR / filename)).face
        assert all(ord(character) in face.charToGlyph for character in "ӘәҒғҚқҢңӨөҰұҮүҺһІі")
