from tests.factories import auth_headers


async def open_case(client, ctx, *, user=None, **changes):
    data = {
        "category": "ticket_delivery",
        "subject": "Missing ticket",
        "body": "Please help.",
        "event_id": str(ctx.event_id),
        **changes,
    }
    return await client.post(
        "/api/v1/support/cases", json=data, headers=auth_headers(user or ctx.buyer)
    )


async def opened_case(client, ctx, **changes):
    response = await open_case(client, ctx, **changes)
    assert response.status_code == 201, response.text
    return response.json()


async def reply(client, case, user, **changes):
    return await client.post(
        f"/api/v1/support/cases/{case['id']}/messages",
        json={"body": "A helpful reply", **changes},
        headers=auth_headers(user),
    )


async def set_status(client, case, user, status):
    return await client.patch(
        f"/api/v1/support/cases/{case['id']}/status",
        json={"status": status},
        headers=auth_headers(user),
    )


async def assign(client, case, user, target):
    return await client.patch(
        f"/api/v1/support/cases/{case['id']}/assignment",
        json={"assigned_to_user_id": str(target.id) if target else None},
        headers=auth_headers(user),
    )
