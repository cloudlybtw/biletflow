"""On-demand, one-page A4 ticket. The QR uses the canonical admission token."""

import io
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from app.modules.tickets.schemas import TicketOut

FONT_DIR = Path(__file__).with_name("fonts")
# Register before request threads start. Fonts ship with the app for Docker/local parity.
pdfmetrics.registerFont(TTFont("TicketSans", str(FONT_DIR / "NotoSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("TicketSansBold", str(FONT_DIR / "NotoSans-Bold.ttf")))


def text_block(
    page: canvas.Canvas,
    value: str,
    x: float,
    top: float,
    width: float,
    height: float,
    *,
    size: int = 14,
    bold: bool = False,
) -> None:
    """Wrap and fit user text inside a bounded area without interpreting markup."""
    font = "TicketSansBold" if bold else "TicketSans"
    value = " ".join(value.split())
    for font_size in range(size, 7, -1):
        style = ParagraphStyle(
            "ticket",
            fontName=font,
            fontSize=font_size,
            leading=font_size * 1.3,
            splitLongWords=True,
        )
        paragraph = Paragraph(escape(value), style)
        _, actual_height = paragraph.wrap(width, height)
        if actual_height <= height:
            paragraph.drawOn(page, x, top - actual_height)
            return
    # Unusually long imported venue values still cannot overlap the QR or footer.
    while value:
        value = value[:-1]
        paragraph = Paragraph(escape(value) + "...", style)
        _, actual_height = paragraph.wrap(width, height)
        if actual_height <= height:
            paragraph.drawOn(page, x, top - actual_height)
            return


def label(page: canvas.Canvas, value: str, x: float, y: float) -> None:
    page.setFont("TicketSansBold", 9)
    page.drawString(x, y, value)


def qr(page: canvas.Canvas, token: str, x: float, y: float, size: float) -> None:
    # Draw vector modules: crisp at any print resolution, with four-module quiet zone.
    code = segno.make(token, error="h", micro=False)
    matrix = list(code.matrix_iter(scale=1, border=4))
    module = size / len(matrix)
    page.setFillColorRGB(1, 1, 1)
    page.rect(x, y, size, size, stroke=0, fill=1)
    page.setFillColorRGB(0, 0, 0)
    path = page.beginPath()
    for row_index, row in enumerate(matrix):
        for column, dark in enumerate(row):
            if dark:
                path.rect(
                    x + column * module, y + (len(matrix) - row_index - 1) * module, module, module
                )
    page.drawPath(path, stroke=0, fill=1)


def render(ticket: TicketOut) -> bytes:
    stream = io.BytesIO()
    page = canvas.Canvas(stream, pagesize=A4, pageCompression=1)
    page.setTitle(f"BiletFlow ticket {ticket.ticket_code}")
    page.setAuthor("BiletFlow")
    width, height = A4
    left, right = 42, width - 42
    page.setFillColorRGB(0, 0, 0)
    page.setStrokeColorRGB(0, 0, 0)
    page.setFont("TicketSansBold", 26)
    page.drawString(left, height - 53, "BiletFlow")
    label(page, "ADMISSION TICKET", left, height - 75)
    page.line(left, height - 90, right, height - 90)

    text_block(page, ticket.event.title, left, height - 107, right - left, 100, size=26, bold=True)
    timezone = ZoneInfo(ticket.event.timezone)
    start = ticket.event.starts_at.astimezone(timezone)
    end = ticket.event.ends_at.astimezone(timezone)
    label(page, "DATE AND TIME", left, 621)
    text_block(
        page,
        f"{start:%d %b %Y, %H:%M} - {end:%d %b %Y, %H:%M}\n({ticket.event.timezone})",
        left,
        606,
        right - left,
        48,
    )
    label(page, "VENUE", left, 548)
    venue = (
        ", ".join(
            filter(
                None, [ticket.event.venue_name, ticket.event.venue_address, ticket.event.venue_city]
            )
        )
        or "Venue to be announced"
    )
    text_block(page, venue, left, 533, right - left, 48)
    label(page, "ATTENDEE", left, 474)
    text_block(page, ticket.attendee_name, left, 459, right - left, 47, size=20, bold=True)
    label(page, "TICKET TYPE", left, 401)
    text_block(page, ticket.ticket_type_name, left, 386, right - left, 42, size=17)
    label(page, "SEAT", left, 334)
    seat = (
        " / ".join(
            filter(
                None,
                [
                    f"Section {ticket.seat_section_label}" if ticket.seat_section_label else None,
                    f"Row {ticket.seat_row_label}" if ticket.seat_row_label else None,
                    f"Seat {ticket.seat_number_label}" if ticket.seat_number_label else None,
                ],
            )
        )
        or "General admission"
    )
    text_block(page, seat, left, 319, right - left, 42)
    page.line(left, 263, right, 263)

    label(page, "TICKET IDENTIFIER", left, 241)
    text_block(page, ticket.ticket_code, left, 226, 290, 49, size=18, bold=True)
    label(page, "CURRENT STATUS", left, 158)
    text_block(
        page, ticket.status.value.replace("_", " ").upper(), left, 143, 290, 30, size=16, bold=True
    )
    text_block(
        page,
        "Present this QR at the entrance.\nDigital and printed copies share one admission.",
        left,
        99,
        290,
        41,
        size=10,
    )
    qr(page, ticket.qr_token, right - 170, 70, 170)
    # Keep the footer outside the QR quiet zone.
    page.setFont("TicketSans", 8)
    page.drawString(left, 30, "Print on A4 paper at 100% scale. Online verification required.")
    page.showPage()
    page.save()
    return stream.getvalue()
