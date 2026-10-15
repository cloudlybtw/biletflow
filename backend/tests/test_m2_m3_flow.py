from datetime import UTC, datetime, timedelta

from tests.factories import auth_headers, create_organizer, create_verified_user


async def test_event_to_campaign_qr_checkout_payment_and_tickets(client, db_session):
    owner = await create_verified_user(db_session)
    await create_organizer(db_session, owner)
    await db_session.commit()
    headers = auth_headers(owner)
    start = datetime.now(UTC) + timedelta(days=30)
    event_response = await client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "title": "Full API walkthrough",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
            "venue_id": "20000000-0000-0000-0000-000000000001",
        },
    )
    assert event_response.status_code == 201, event_response.text
    event = event_response.json()
    path = f"/api/v1/events/{event['id']}"
    ticket_response = await client.post(
        path + "/ticket-types",
        headers=headers,
        json={"name": "Regular", "quantity_total": 10, "price_amount": 3000},
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()
    assert (await client.post(path + "/publish", headers=headers)).status_code == 200
    assert (await client.get(f"/api/v1/events/by-slug/{event['slug']}")).status_code == 200
    campaign_response = await client.post(
        path + "/campaigns",
        headers=headers,
        json={
            "name": "Launch",
            "discount_type": "percent",
            "discount_value": 15,
            "ticket_type_ids": [ticket["id"]],
            "code": "LAUNCH15",
        },
    )
    assert campaign_response.status_code == 201, campaign_response.text
    campaign = campaign_response.json()
    campaign_path = path + f"/campaigns/{campaign['id']}"
    assert (await client.post(campaign_path + "/activate", headers=headers)).status_code == 200
    qr_response = await client.post(campaign_path + "/qr", headers=headers, json={})
    assert qr_response.status_code == 201, qr_response.text
    qr = qr_response.json()
    assert (await client.get(qr["image_url"], headers=headers)).headers[
        "content-type"
    ] == "image/png"
    link = await client.get(f"/api/v1/campaign-links/{qr['token']}")
    assert link.status_code == 200 and link.json()["event_slug"] == event["slug"]
    preview = await client.post(
        path + "/promo/validate",
        json={
            "code": link.json()["promo_code"],
            "items": [{"ticket_type_id": ticket["id"], "quantity": 2}],
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["discount_amount"] == 900
    assert preview.json()["total_amount"] == 5100

    assert (
        await client.post("/api/v1/organizers/me/identity-verification", headers=headers)
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/organizers/me/payout-accounts",
            headers=headers,
            json={"account_holder_name": "Demo Organizer", "external_account_ref": "KZ12345678"},
        )
    ).status_code == 201
    assert (
        await client.post(path + "/paid-sales/terms", headers=headers, json={"accepted": True})
    ).status_code == 200
    activation_payment = await client.post(path + "/paid-sales/pay", headers=headers)
    assert activation_payment.status_code == 201, activation_payment.text
    assert (
        await client.post(
            f"/api/v1/payments/{activation_payment.json()['id']}/simulate",
            headers=headers,
            json={"outcome": "success"},
        )
    ).status_code == 200
    activated = await client.post(path + "/paid-sales/activate", headers=headers, json={})
    assert activated.status_code == 200, activated.text
    buyer = await create_verified_user(db_session)
    await db_session.commit()
    buyer_headers = auth_headers(buyer)
    order_response = await client.post(
        path + "/orders",
        headers=buyer_headers,
        json={
            "promo_code": link.json()["promo_code"],
            "items": [{"ticket_type_id": ticket["id"], "quantity": 2}],
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["status"] == "pending" and order["total_amount"] == 5100
    payment_response = await client.post(f"/api/v1/orders/{order['id']}/pay", headers=buyer_headers)
    assert payment_response.status_code == 201, payment_response.text
    payment = payment_response.json()
    success = await client.post(
        f"/api/v1/payments/{payment['id']}/simulate",
        headers=buyer_headers,
        json={"outcome": "success"},
    )
    assert success.status_code == 200 and success.json()["status"] == "succeeded"
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=buyer_headers)).json()
    assert detail["status"] == "completed" and len(detail["ticket_ids"]) == 2
    ticket_detail = await client.get(
        f"/api/v1/tickets/{detail['ticket_ids'][0]}", headers=buyer_headers
    )
    assert ticket_detail.status_code == 200 and ticket_detail.json()["qr_token"].startswith("bft_")
    assert (await client.get(ticket_detail.json()["qr_image_url"], headers=buyer_headers)).headers[
        "content-type"
    ] == "image/png"
    pdf = await client.get(ticket_detail.json()["pdf_url"], headers=buyer_headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    case = await client.post(
        "/api/v1/support/cases",
        headers=buyer_headers,
        json={
            "ticket_id": detail["ticket_ids"][0],
            "category": "ticket_delivery",
            "subject": "Print my ticket",
            "body": "Where can I download the PDF?",
        },
    )
    assert case.status_code == 201, case.text
    reply = await client.post(
        f"/api/v1/support/cases/{case.json()['id']}/messages",
        headers=headers,
        json={"body": "Use the PDF download in your tickets."},
    )
    assert reply.status_code == 201
    inbox = await client.get("/api/v1/notifications", headers=buyer_headers)
    assert inbox.status_code == 200 and inbox.json()["total"] == 1
    assert (
        await client.patch(
            f"/api/v1/support/cases/{case.json()['id']}/status",
            headers=headers,
            json={"status": "resolved"},
        )
    ).status_code == 200
    scanned = await client.post(
        f"/api/v1/checkin/scan?event_id={event['id']}",
        headers=headers,
        json={"token": ticket_detail.json()["qr_token"]},
    )
    assert scanned.status_code == 201 and scanned.json()["result"] == "valid"
    rejected = await client.post(
        f"/api/v1/checkin/scan?event_id={event['id']}", headers=headers, json={"token": qr["token"]}
    )
    assert rejected.status_code == 201 and rejected.json()["result"] == "campaign_code_rejected"
    dashboard = await client.get(path + "/analytics/summary", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    metrics = dashboard.json()
    assert metrics["sold"] == 2 and metrics["remaining"] == 8
    assert metrics["gross_amount"] == 6000 and metrics["discount_amount"] == 900
    assert metrics["net_amount"] == 5100 and metrics["simulated"] is True
    assert metrics["checked_in"] == 1 and metrics["absent"] == 1
    campaign_report = await client.get(path + "/analytics/campaigns", headers=headers)
    assert campaign_report.json()["items"][0]["redemptions"] == 1
    refund = await client.post(path + f"/orders/{order['id']}/refunds", headers=headers, json={})
    assert refund.status_code == 201 and refund.json()["simulated"] is True
    assert refund.json()["amount"] == 5100
    dashboard = await client.get(path + "/analytics/summary", headers=headers)
    assert dashboard.json()["refund_amount"] == 5100 and dashboard.json()["net_amount"] == 0
    assert dashboard.json()["sold"] == dashboard.json()["registered"] == 0
    timeline = await client.get(path + "/history", headers=headers, params={"limit": 100})
    assert timeline.status_code == 200
    assert {
        "event.published",
        "promo_code.created",
        "support.status_changed",
        "ticket.checked_in",
        "refund.completed",
    } <= {row["action_type"] for row in timeline.json()["items"]}
    assert (await client.get(path + f"/orders/{order['id']}", headers=headers)).json()[
        "status"
    ] == "refunded"
    cancelled = await client.post(path + "/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["classification"] == "Cancelled"
    duplicate = await client.post(path + "/duplicate", headers=headers)
    assert duplicate.status_code == 201
    copied_orders = await client.get(
        f"/api/v1/events/{duplicate.json()['id']}/orders", headers=headers
    )
    assert copied_orders.json()["total"] == 0
