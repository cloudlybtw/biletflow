import asyncio
import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update

from app.core.errors import AppError
from app.core.pagination import Pagination
from app.core.reporting import EXPORT_LIMIT, ReportFilters, csv_response
from app.modules.analytics import service
from app.modules.events.models import Event, EventVisibility
from app.modules.users.models import StaffAssignment, User, UserStatus
from tests.analytics.test_reports import fetch
from tests.factories import auth_headers, complete_purchase, create_event, create_ticket_type


async def test_fully_discounted_cancelled_and_hidden_inventory_report(
    client, reporting_context, db_session
):
    c = reporting_context
    campaign = await client.post(
        f"/api/v1/events/{c.event_id}/campaigns",
        headers=auth_headers(c.owner),
        json={"name": "Gift", "discount_type": "percent", "discount_value": 100},
    )
    campaign = campaign.json()
    await client.post(
        f"/api/v1/events/{c.event_id}/campaigns/{campaign['id']}/activate",
        headers=auth_headers(c.owner),
    )
    order = await complete_purchase(client, c, promo_code=campaign["promo_codes"][0]["code"])
    assert order["total_amount"] == 0
    hidden = await create_ticket_type(
        db_session, c.event_id, price_amount=500, name="Hidden", is_hidden=True, quantity_total=7
    )
    await db_session.commit()
    summary = await fetch(client, c)
    assert (
        summary["ticket_capacity"] == 107
        and summary["gross_amount"] == summary["discount_amount"] == 1000
    )
    assert summary["net_collected_amount"] == 0 and summary["sold"] == 1
    response = await client.post(
        f"/api/v1/events/{c.event_id}/orders/{order['id']}/cancel",
        headers=auth_headers(c.owner),
        json={},
    )
    assert response.status_code == 200, response.text
    summary = await fetch(client, c)
    assert summary["tickets"] == 1 and summary["sold"] == summary["registered"] == 0
    assert (
        summary["gross_amount"] == summary["discount_amount"] == 1000
        and summary["refund_amount"] == 0
    )
    hidden_report = await fetch(client, c, ticket_type_id=str(hidden.id))
    assert hidden_report["capacity"] == 7 and hidden_report["sold"] == 0


async def test_sales_snapshot_prices_and_csv_reconciliation(client, reporting_context):
    c = reporting_context
    await complete_purchase(client, c)
    await client.patch(
        f"/api/v1/events/{c.event_id}/ticket-types/{c.ticket_type.id}",
        headers=auth_headers(c.owner),
        json={"price_amount": 2000},
    )
    await complete_purchase(client, c)
    summary = await fetch(client, c)
    assert summary["gross_amount"] == 3000
    response = await client.get(
        f"/api/v1/events/{c.event_id}/analytics/sales/ticket-types.csv",
        headers=auth_headers(c.owner),
    )
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert sum(int(r["gross_amount"]) for r in rows) == summary["gross_amount"]
    assert all(r["currency"] == "KZT" and r["simulated"] == "True" for r in rows)


async def test_private_suspended_past_event_and_revoked_or_suspended_actor(
    client, reporting_context, db_session
):
    c = reporting_context
    await complete_purchase(client, c)
    await db_session.execute(
        update(Event)
        .where(Event.id == c.event_id)
        .values(
            visibility=EventVisibility.PRIVATE,
            is_suspended=True,
            starts_at=datetime.now(UTC) - timedelta(days=2),
            ends_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()
    assert (await fetch(client, c))["gross_amount"] == 1000
    response = await client.get(
        f"/api/v1/events/{c.event_id}/analytics/summary", headers=auth_headers(c.admin)
    )
    assert response.status_code == 200
    await db_session.execute(
        update(StaffAssignment)
        .where(StaffAssignment.id == c.assignment.id)
        .values(revoked_at=datetime.now(UTC))
    )
    await db_session.execute(
        update(User).where(User.id == c.owner.id).values(status=UserStatus.SUSPENDED)
    )
    await db_session.commit()
    url = f"/api/v1/events/{c.event_id}/analytics/summary"
    assert (await client.get(url, headers=auth_headers(c.co))).status_code == 404
    assert (await client.get(url, headers=auth_headers(c.owner))).status_code == 403


async def test_report_snapshot_races_payment_refund_and_checkin(client, reporting_context):
    c = reporting_context
    purchase, summary = await asyncio.gather(complete_purchase(client, c), fetch(client, c))
    assert summary["gross_amount"] in [0, 1000]
    assert summary["gross_amount"] == summary["net_amount"]
    scan, summary = await asyncio.gather(
        client.post(
            f"/api/v1/checkin/scan?event_id={c.event_id}",
            headers=auth_headers(c.event_admin),
            json={"ticket_id": purchase["ticket_ids"][0]},
        ),
        fetch(client, c),
    )
    assert scan.status_code == 201
    assert summary["registered"] == summary["checked_in"] + summary["absent"] == 1
    refund, summary = await asyncio.gather(
        client.post(
            f"/api/v1/events/{c.event_id}/orders/{purchase['id']}/refunds",
            headers=auth_headers(c.owner),
            json={},
        ),
        fetch(client, c),
    )
    assert refund.status_code == 201, refund.text
    assert (
        summary["sold"],
        summary["registered"],
        summary["net_amount"],
        summary["refund_amount"],
    ) in [(1, 1, 1000, 0), (0, 0, 0, 1000)]


async def test_activation_payment_not_counted_as_ticket_sales(client, reporting_context):
    c = reporting_context
    response = await client.post(
        f"/api/v1/events/{c.event_id}/paid-sales/pay", headers=auth_headers(c.owner)
    )
    assert response.status_code == 201, response.text
    payment = response.json()
    response = await client.post(
        f"/api/v1/payments/{payment['id']}/simulate",
        headers=auth_headers(c.owner),
        json={"outcome": "success"},
    )
    assert response.status_code == 200, response.text
    report = await fetch(client, c)
    assert report["gross_amount"] == report["orders"] == report["net_amount"] == 0


async def test_csv_export_bound_and_formula_safety():
    for value in ["=1+1", " +SUM(A1)", "\t@SUM(A1)", '-HYPERLINK("x")']:
        response = csv_response([{"name": value}], ["name"], "test")
        rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8-sig"))))
        assert rows[0]["name"].startswith("'")
    with pytest.raises(AppError) as exc:
        csv_response([{}] * (EXPORT_LIMIT + 1), ["name"], "test")
    assert exc.value.code == "EXPORT_TOO_LARGE"


async def test_money_above_float_precision_remains_exact(client, reporting_context):
    c = reporting_context
    price = 9_007_199_254_740_993
    response = await client.patch(
        f"/api/v1/events/{c.event_id}/ticket-types/{c.ticket_type.id}",
        headers=auth_headers(c.owner),
        json={"price_amount": price},
    )
    assert response.status_code == 200, response.text
    await complete_purchase(client, c)
    for path in ["summary", "sales/daily", "sales/ticket-types"]:
        response = await fetch(client, c, path)
        row = response["items"][0] if "items" in response else response
        assert row["gross_amount"] == row["net_amount"] == price


async def test_representative_sales_plan_uses_existing_event_order_index(
    db_session, reporting_context, client
):
    c = reporting_context
    other_event = await create_event(db_session, c.profile)
    other_type = await create_ticket_type(db_session, other_event, quantity_total=20000)
    # Representative committed historical data in the disposable test database.
    # No production/demo database is touched and the normal fixture truncates it.
    for event_id, type_id, count in [
        (c.event_id, c.ticket_type.id, 100),
        (other_event, other_type.id, 10000),
    ]:
        await db_session.execute(
            text("""
        WITH os AS (
          INSERT INTO orders(order_number,event_id,buyer_user_id,buyer_email,buyer_name,status,
            subtotal_amount,total_amount,placed_at)
          SELECT 'PERF-'||gen_random_uuid(), :event_id,:buyer_id,'perf@example.com','Performance',
            'completed',1000,1000,now() - g * interval '1 minute'
          FROM generate_series(1,:count) g RETURNING id
        ), items AS (
          INSERT INTO order_items(order_id,ticket_type_id,quantity,unit_price_amount,line_total)
          SELECT id,:type_id,1,1000,1000 FROM os RETURNING id
        ), people AS (
          INSERT INTO attendees(order_item_id,full_name)
          SELECT id,'Performance' FROM items RETURNING id,order_item_id
        ) INSERT INTO tickets(ticket_code,qr_token,event_id,ticket_type_id,order_item_id,attendee_id)
          SELECT 'PERF-'||id,'bft_'||id,:event_id,:type_id,order_item_id,id FROM people
        """),
            dict(event_id=event_id, type_id=type_id, buyer_id=c.buyer.id, count=count),
        )
    await db_session.execute(text("ANALYZE orders, order_items, tickets, refunds"))
    await db_session.commit()
    params = await service.parameters(db_session, c.event_id, ReportFilters())
    plan = (
        await db_session.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                + service.report_query("daily")
                + " SELECT * FROM result"
            ),
            params,
        )
    ).scalar_one()
    import json

    if isinstance(plan, str):
        plan = json.loads(plan)

    def nodes(node):
        yield node
        for child in node.get("Plans", []):
            yield from nodes(child)

    indexes = {node.get("Index Name") for node in nodes(plan[0]["Plan"])}
    assert "ix_orders_event_placed" in indexes
    assert not any(node.get("Node Type") == "LockRows" for node in nodes(plan[0]["Plan"]))
    reports, total = await service.report(
        db_session, c.event_id, ReportFilters(), "daily", Pagination(100, 0)
    )
    assert sum(row["gross_amount"] for row in reports) == 100000
    assert total >= 1
    exported = await client.get("/api/v1/admin/orders/export.csv", headers=auth_headers(c.admin))
    assert exported.status_code == 400 and exported.json()["error"]["code"] == "EXPORT_TOO_LARGE"
    exported = await client.get(
        "/api/v1/admin/orders/export.csv",
        headers=auth_headers(c.admin),
        params={"event_id": str(c.event_id)},
    )
    assert exported.status_code == 200, exported.text
    assert len(list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))) == 100
