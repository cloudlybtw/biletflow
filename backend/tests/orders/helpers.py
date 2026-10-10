from tests.factories import auth_headers


def cart(context, quantity=1, **extra):
    return {
        "items": [{"ticket_type_id": str(context.ticket_type.id), "quantity": quantity}],
        **extra,
    }


async def checkout(client, context, *, buyer=None, data=None, **extra):
    return await client.post(
        f"/api/v1/events/{context.event_id}/orders",
        json=data or cart(context, **extra),
        headers=auth_headers(buyer or context.buyer),
    )


async def placed_order(client, context, **extra):
    response = await checkout(client, context, **extra)
    assert response.status_code == 201, response.text
    return response.json()


async def pay(client, context, order_id):
    response = await client.post(
        f"/api/v1/orders/{order_id}/pay", headers=auth_headers(context.buyer)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def simulate(client, context, payment_id, outcome="success"):
    return await client.post(
        f"/api/v1/payments/{payment_id}/simulate",
        json={"outcome": outcome},
        headers=auth_headers(context.buyer),
    )
