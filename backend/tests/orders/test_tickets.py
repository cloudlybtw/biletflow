import io
import uuid

from PIL import Image
from sqlalchemy import update

from app.modules.ticketing.models import TicketType
from tests.factories import auth_headers
from tests.orders.helpers import placed_order


async def test_buyer_only_order_ticket_and_qr_access(client, db_session, context):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
    )
    await db_session.commit()
    order = await placed_order(client, context, quantity=2)
    ticket_id = order["ticket_ids"][0]
    for path in [
        f"/api/v1/orders/{order['id']}",
        f"/api/v1/tickets/{ticket_id}",
        f"/api/v1/tickets/{ticket_id}/qr.png",
    ]:
        assert (await client.get(path)).status_code == 401
        assert (
            await client.get(path, headers=auth_headers(context.other_buyer))
        ).status_code == 404
        assert (await client.get(path, headers=auth_headers(context.buyer))).status_code == 200
    assert (
        await client.post(
            f"/api/v1/orders/{order['id']}/pay", headers=auth_headers(context.other_buyer)
        )
    ).status_code == 404
    listing = await client.get(
        "/api/v1/tickets", params={"limit": 1}, headers=auth_headers(context.buyer)
    )
    assert listing.json()["total"] == 2 and len(listing.json()["items"]) == 1
    assert (await client.get("/api/v1/tickets", headers=auth_headers(context.other_buyer))).json()[
        "total"
    ] == 0
    detail = (
        await client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers(context.buyer))
    ).json()
    assert detail["attendee_name"] == context.buyer.full_name
    assert detail["event"]["id"] == str(context.event_id)
    assert detail["qr_token"].startswith("bft_")
    assert detail["seat_id"] is None
    qr = await client.get(detail["qr_image_url"], headers=auth_headers(context.buyer))
    assert qr.headers["content-type"] == "image/png"
    assert qr.headers["cache-control"] == "private, no-store"
    with Image.open(io.BytesIO(qr.content)) as image:
        assert image.width == image.height
        assert image.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
    assert (
        await client.get(f"/api/v1/tickets/{uuid.uuid4()}", headers=auth_headers(context.buyer))
    ).status_code == 404


async def test_attendee_email_does_not_grant_purchase_access(client, db_session, context):
    await db_session.execute(
        update(TicketType).where(TicketType.id == context.ticket_type.id).values(price_amount=0)
    )
    await db_session.commit()
    data = {
        "items": [
            {
                "ticket_type_id": str(context.ticket_type.id),
                "attendees": [{"full_name": "Gift recipient", "email": context.other_buyer.email}],
            }
        ]
    }
    order = await placed_order(client, context, data=data)
    ticket = order["ticket_ids"][0]
    assert (
        await client.get(f"/api/v1/tickets/{ticket}", headers=auth_headers(context.other_buyer))
    ).status_code == 404
    buyer_ticket = await client.get(
        f"/api/v1/tickets/{ticket}", headers=auth_headers(context.buyer)
    )
    assert buyer_ticket.json()["attendee_name"] == "Gift recipient"
