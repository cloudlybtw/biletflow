import asyncio
import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.db.settings import PlatformSetting
from app.modules.events.models import Event
from app.modules.orders.models import Order
from app.modules.ticketing.models import TicketType
from tests.factories import auth_headers, complete_purchase, create_event, create_ticket_type
from tests.orders.helpers import pay, placed_order, simulate

REPORTS = ["summary", "attendance", "sales/daily", "sales/ticket-types", "campaigns", "promo-codes"]


async def fetch(client, context, path="summary", **params):
    response = await client.get(
        f"/api/v1/events/{context.event_id}/analytics/{path}",
        headers=auth_headers(context.owner),
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("path", REPORTS)
async def test_empty_event_reports_and_csv(client, reporting_context, path):
    c = reporting_context
    body = await fetch(client, c, path)
    if "items" in body:
        assert body["total"] == (1 if path == "sales/ticket-types" else 0)
    response = await client.get(
        f"/api/v1/events/{c.event_id}/analytics/{path}.csv", headers=auth_headers(c.owner)
    )
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "private" in response.headers["cache-control"]
    assert list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


@pytest.mark.parametrize("path", REPORTS + [p + ".csv" for p in REPORTS])
async def test_reports_deny_unrelated_buyer_and_checkin_staff(client, reporting_context, path):
    c = reporting_context
    url = f"/api/v1/events/{c.event_id}/analytics/{path}"
    for user, expected in [(c.buyer, 404), (c.event_admin, 403), (c.support, 403)]:
        response = await client.get(url, headers=auth_headers(user))
        assert response.status_code == expected, response.text
    assert (await client.get(url)).status_code == 401


@pytest.mark.parametrize("path", REPORTS)
async def test_coorganizer_and_platform_admin_read_reports(client, reporting_context, path):
    c = reporting_context
    for user in [c.co, c.admin]:
        response = await client.get(
            f"/api/v1/events/{c.event_id}/analytics/{path}", headers=auth_headers(user)
        )
        assert response.status_code == 200, response.text


async def test_exact_sales_refunds_and_current_inventory(client, reporting_context, db_session):
    c = reporting_context
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "processing_fee_percent")
        .values(value=2)
    )
    await db_session.commit()
    order = await complete_purchase(client, c, quantity=2)
    before = await fetch(client, c)
    assert {
        k: before[k]
        for k in [
            "tickets",
            "sold",
            "gross_amount",
            "fee_amount",
            "net_amount",
            "net_collected_amount",
            "remaining",
        ]
    } == {
        "tickets": 2,
        "sold": 2,
        "gross_amount": 2000,
        "fee_amount": 40,
        "net_amount": 2000,
        "net_collected_amount": 2040,
        "remaining": 98,
    }
    response = await client.post(
        f"/api/v1/events/{c.event_id}/orders/{order['id']}/refunds",
        json={},
        headers=auth_headers(c.owner),
    )
    assert response.status_code == 201, response.text
    after = await fetch(client, c)
    assert after["gross_amount"] == 2000 and after["tickets"] == 2
    assert (
        after["refund_amount"] == 2040
        and after["ticket_refund_amount"] == 2000
        and after["fee_refund_amount"] == 40
    )
    assert (
        after["net_amount"]
        == after["net_collected_amount"]
        == after["sold"]
        == after["registered"]
        == 0
    )
    assert after["remaining"] == 100 and after["simulated"] is True


async def test_pending_failed_expired_orders_and_activation_fees_excluded(
    client, reporting_context, db_session
):
    c = reporting_context
    order = await placed_order(client, c)
    payment = await pay(client, c, order["id"])
    await simulate(client, c, payment["id"], "failure")
    report = await fetch(client, c)
    assert report["orders"] == report["tickets"] == report["gross_amount"] == 0
    assert report["reserved"] == 1 and report["remaining"] == 99
    # Analytics must not lazily expire stale reservations.
    await db_session.execute(
        update(Order)
        .where(Order.id == uuid.UUID(order["id"]))
        .values(expires_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.commit()
    assert (await fetch(client, c))["reserved"] == 1
    assert (await db_session.get(Order, uuid.UUID(order["id"]))).status == "awaiting_payment"


async def test_ticket_type_fee_and_refund_allocation_reconciles(
    client, reporting_context, db_session
):
    c = reporting_context
    other = await create_ticket_type(
        db_session, c.event_id, price_amount=1001, name="VIP", is_hidden=False
    )
    await db_session.execute(
        update(PlatformSetting)
        .where(PlatformSetting.key == "processing_fee_percent")
        .values(value=1)
    )
    await db_session.commit()
    order = await complete_purchase(
        client,
        c,
        data={
            "items": [
                {"ticket_type_id": str(c.ticket_type.id), "quantity": 1},
                {"ticket_type_id": str(other.id), "quantity": 1},
            ]
        },
    )
    report = await fetch(client, c, "sales/ticket-types")
    assert sum(r["fee_amount"] for r in report["items"]) == 20
    for row in report["items"]:
        filtered = await fetch(client, c, ticket_type_id=row["ticket_type_id"])
        assert filtered["gross_amount"] == row["gross_amount"]
        assert filtered["fee_amount"] == row["fee_amount"]
    await client.post(
        f"/api/v1/events/{c.event_id}/orders/{order['id']}/refunds",
        json={},
        headers=auth_headers(c.owner),
    )
    report = await fetch(client, c, "sales/ticket-types")
    assert sum(r["refund_amount"] for r in report["items"]) == 2021
    assert all(r["net_collected_amount"] == 0 for r in report["items"])


async def test_utc_daily_boundaries_and_current_inventory_independent_of_date(
    client, reporting_context, db_session
):
    c = reporting_context
    orders = [await complete_purchase(client, c) for _ in range(2)]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for order, when in zip(orders, [start, start + timedelta(days=1)], strict=True):
        await db_session.execute(
            update(Order).where(Order.id == uuid.UUID(order["id"])).values(placed_at=when)
        )
    await db_session.commit()
    body = await fetch(
        client,
        c,
        "sales/daily",
        date_from="2026-01-01T05:00:00+05:00",
        date_to="2026-01-02T00:00:00Z",
    )
    assert (
        body["total"] == 1
        and body["items"][0]["day"] == "2026-01-01"
        and body["items"][0]["gross_amount"] == 1000
    )
    summary = await fetch(
        client, c, date_from=start.isoformat(), date_to=(start + timedelta(days=1)).isoformat()
    )
    assert summary["tickets"] == 1 and summary["sold"] == 2
    for params in [
        {"date_from": "2026-01-01"},
        {"date_from": "2026-01-02T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"},
    ]:
        response = await client.get(
            f"/api/v1/events/{c.event_id}/analytics/summary",
            headers=auth_headers(c.owner),
            params=params,
        )
        assert response.status_code == 422


async def test_campaign_completed_redemptions_exclude_claims_and_refunds(client, reporting_context):
    c = reporting_context
    url = f"/api/v1/events/{c.event_id}/campaigns"
    campaign = await client.post(
        url,
        headers=auth_headers(c.owner),
        json={"name": "Winter", "discount_type": "percent", "discount_value": 10},
    )
    assert campaign.status_code == 201, campaign.text
    campaign = campaign.json()
    await client.post(url + f"/{campaign['id']}/activate", headers=auth_headers(c.owner))
    code = campaign["promo_codes"][0]["code"]
    first = await complete_purchase(client, c, promo_code=code, quantity=2)
    await placed_order(client, c, promo_code=code)
    before = await fetch(client, c, "campaigns")
    row = before["items"][0]
    assert row["redemptions"] == row["orders"] == 1 and row["tickets"] == 2
    assert (
        row["gross_amount"] == 2000 and row["discount_amount"] == 200 and row["net_amount"] == 1800
    )
    await client.post(
        f"/api/v1/events/{c.event_id}/orders/{first['id']}/refunds",
        json={},
        headers=auth_headers(c.owner),
    )
    row = (await fetch(client, c, "campaigns"))["items"][0]
    assert row["redemptions"] == row["gross_amount"] == row["net_amount"] == 0
    assert row["refunded_orders"] == 1 and row["historical_refund_amount"] == 1800
    promo = (await fetch(client, c, "promo-codes"))["items"][0]
    assert promo["promo_code"] == code and promo["historical_refund_amount"] == 1800
    overall = await fetch(client, c)
    assert (
        overall["gross_amount"] == 2000
        and overall["discount_amount"] == 200
        and overall["net_amount"] == 0
    )


async def test_attendance_reversal_and_event_cancellation(client, reporting_context):
    c = reporting_context
    order = await complete_purchase(client, c, quantity=2)
    scan = await client.post(
        f"/api/v1/checkin/scan?event_id={c.event_id}",
        json={"ticket_id": order["ticket_ids"][0]},
        headers=auth_headers(c.event_admin),
    )
    assert scan.status_code == 201, scan.text
    report = await fetch(client, c, "attendance")
    assert (
        report["registered"] == 2
        and report["checked_in"] == 1
        and report["absent"] == 1
        and report["check_in_percent"] == 50
    )
    undo = await client.post(
        f"/api/v1/events/{c.event_id}/checkin/records/{scan.json()['record_id']}/reverse",
        json={},
        headers=auth_headers(c.event_admin),
    )
    assert undo.status_code == 201, undo.text
    assert (await fetch(client, c, "attendance"))["checked_in"] == 0
    await client.post(f"/api/v1/events/{c.event_id}/cancel", headers=auth_headers(c.owner))
    assert (await fetch(client, c))["registered"] == 0


async def test_read_only_reports_do_not_wait_for_checkout_locks(
    client, reporting_context, test_sessionmaker
):
    c = reporting_context
    order = await complete_purchase(client, c)
    async with test_sessionmaker() as lock_session:
        await lock_session.execute(select(Event).where(Event.id == c.event_id).with_for_update())
        await lock_session.execute(
            select(Order).where(Order.id == uuid.UUID(order["id"])).with_for_update()
        )
        await lock_session.execute(
            select(TicketType).where(TicketType.id == c.ticket_type.id).with_for_update()
        )
        reports = await asyncio.wait_for(
            asyncio.gather(*(fetch(client, c, path) for path in REPORTS)), timeout=5
        )
        assert len(reports) == 6
        await lock_session.rollback()


async def test_foreign_ticket_type_is_hidden_and_pagination_total_retained(
    client, reporting_context, db_session
):
    c = reporting_context
    foreign = await create_event(db_session)
    foreign_type = await create_ticket_type(db_session, foreign)
    await db_session.commit()
    response = await client.get(
        f"/api/v1/events/{c.event_id}/analytics/summary",
        params={"ticket_type_id": str(foreign_type.id)},
        headers=auth_headers(c.owner),
    )
    assert response.status_code == 404
    report = await fetch(client, c, "sales/ticket-types", offset=200)
    assert report["items"] == [] and report["total"] == 1
