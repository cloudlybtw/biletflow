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
    order_response = await client.post(
        path + "/orders",
        headers=headers,
        json={
            "promo_code": link.json()["promo_code"],
            "items": [{"ticket_type_id": ticket["id"], "quantity": 2}],
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["status"] == "pending" and order["total_amount"] == 5100
    payment_response = await client.post(f"/api/v1/orders/{order['id']}/pay", headers=headers)
    assert payment_response.status_code == 201, payment_response.text
    payment = payment_response.json()
    success = await client.post(
        f"/api/v1/payments/{payment['id']}/simulate", headers=headers, json={"outcome": "success"}
    )
    assert success.status_code == 200 and success.json()["status"] == "succeeded"
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "completed" and len(detail["ticket_ids"]) == 2
    ticket_detail = await client.get(f"/api/v1/tickets/{detail['ticket_ids'][0]}", headers=headers)
    assert ticket_detail.status_code == 200 and ticket_detail.json()["qr_token"].startswith("bft_")
    assert (await client.get(ticket_detail.json()["qr_image_url"], headers=headers)).headers[
        "content-type"
    ] == "image/png"
