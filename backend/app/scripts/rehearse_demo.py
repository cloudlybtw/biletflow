"""Exercise the public HTTP contract against a disposable local demo deployment."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.scripts.seed_demo import DEMO_PASSWORD


def run(base_url: str):
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "web", "api"}:
        raise ValueError("Rehearsal is restricted to a local disposable demo deployment.")
    base = base_url.rstrip("/") + "/api/v1"

    def request(path, *, user=None, data=None, method=None, expected=200, raw=False):
        headers = {"Accept": "application/json"}
        if user:
            headers["Authorization"] = "Bearer " + user["access_token"]
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(
            base + path,
            data=json.dumps(data).encode() if data is not None else None,
            method=method or ("POST" if data is not None else "GET"),
            headers=headers,
        )
        try:
            with urlopen(req, timeout=30) as response:
                status, body = response.status, response.read()
        except HTTPError as error:
            status, body = error.code, error.read()
        if status != expected:
            raise AssertionError(f"{req.method} {path}: expected {expected}, got {status}")
        return body if raw else json.loads(body) if body else None

    owner, buyer, scanner, admin = (
        request("/auth/login", data={"email": email, "password": DEMO_PASSWORD})
        for email in (
            "organizer@example.com",
            "attendee@example.com",
            "eventadmin@example.com",
            "admin@example.com",
        )
    )
    start = datetime.now(UTC) + timedelta(days=21)
    event = request(
        "/events",
        user=owner,
        data={
            "title": "HTTP rehearsal " + datetime.now(UTC).isoformat(),
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
        },
        expected=201,
    )
    path = "/events/" + event["id"]
    ticket_type = request(
        path + "/ticket-types",
        user=owner,
        data={"name": "Regular", "price_amount": 3000, "quantity_total": 10},
        expected=201,
    )
    request(path + "/publish", user=owner, method="POST")
    request(
        path + "/staff",
        user=owner,
        data={"email": "eventadmin@example.com", "role": "event_admin"},
        expected=201,
    )
    request(path + "/paid-sales/terms", user=owner, data={"accepted": True})
    payment = request(path + "/paid-sales/pay", user=owner, method="POST", expected=201)
    request(f"/payments/{payment['id']}/simulate", user=owner, data={"outcome": "success"})
    request(path + "/paid-sales/activate", user=owner, data={})
    campaign = request(
        path + "/campaigns",
        user=owner,
        data={"name": "Rehearsal offer", "discount_type": "percent", "discount_value": 15},
        expected=201,
    )
    campaign_path = path + "/campaigns/" + campaign["id"]
    request(campaign_path + "/activate", user=owner, method="POST")
    qr = request(campaign_path + "/qr", user=owner, data={}, expected=201)
    assert request(qr["image_url"].removeprefix("/api/v1"), user=owner, raw=True).startswith(
        b"\x89PNG"
    )
    link = request("/campaign-links/" + qr["token"])
    items = [{"ticket_type_id": ticket_type["id"], "quantity": 1}]
    preview = request(path + "/promo/validate", data={"code": link["promo_code"], "items": items})
    assert preview["discount_amount"] == 450
    order = request(
        path + "/orders",
        user=buyer,
        data={"items": items, "promo_code": link["promo_code"]},
        expected=201,
    )
    payment = request(f"/orders/{order['id']}/pay", user=buyer, method="POST", expected=201)
    request(f"/payments/{payment['id']}/simulate", user=buyer, data={"outcome": "failure"})
    payment = request(f"/orders/{order['id']}/pay", user=buyer, method="POST", expected=201)
    request(f"/payments/{payment['id']}/simulate", user=buyer, data={"outcome": "success"})
    order = request("/orders/" + order["id"], user=buyer)
    assert order["status"] == "completed" and order["total_amount"] == 2550
    ticket = request("/tickets/" + order["ticket_ids"][0], user=buyer)
    assert request(ticket["pdf_url"].removeprefix("/api/v1"), user=buyer, raw=True).startswith(
        b"%PDF"
    )
    case = request(
        "/support/cases",
        user=buyer,
        data={
            "ticket_id": ticket["id"],
            "category": "ticket_delivery",
            "subject": "Rehearsal ticket",
            "body": "Please confirm my PDF.",
        },
        expected=201,
    )
    request(
        f"/support/cases/{case['id']}/messages",
        user=owner,
        data={"body": "Your PDF is available in My tickets."},
        expected=201,
    )
    scan_path = "/checkin/scan?event_id=" + event["id"]
    for token, expected_result in [
        (ticket["qr_token"], "valid"),
        (ticket["qr_token"], "duplicate"),
        (qr["token"], "campaign_code_rejected"),
    ]:
        assert (
            request(scan_path, user=scanner, data={"token": token}, expected=201)["result"]
            == expected_result
        )
    report = request(path + "/analytics/summary", user=owner)
    assert report["sold"] == 1 and report["checked_in"] == 1 and report["net_amount"] == 2550
    request("/admin/events/" + event["id"] + "/suspend", user=admin, data={"reason": "Rehearsal"})
    request(path + "/orders", user=buyer, data={"items": items}, expected=409)
    request("/admin/events/" + event["id"] + "/unsuspend", user=admin, method="POST")
    request(
        path + f"/orders/{order['id']}/refunds",
        user=owner,
        data={"reason": "Demo completed"},
        expected=201,
    )
    assert (
        request(scan_path, user=scanner, data={"token": ticket["qr_token"]}, expected=201)["result"]
        == "refunded"
    )
    # A separate completed order demonstrates cancellation's automatic refund
    # and event-cancellation email, independently of the explicit refund above.
    cancel_order = request(path + "/orders", user=buyer, data={"items": items}, expected=201)
    cancel_payment = request(
        f"/orders/{cancel_order['id']}/pay", user=buyer, method="POST", expected=201
    )
    request(f"/payments/{cancel_payment['id']}/simulate", user=buyer, data={"outcome": "success"})
    request(path + "/cancel", user=owner, method="POST")
    assert request("/orders/" + cancel_order["id"], user=buyer)["status"] == "refunded"
    assert b"STATUS:CANCELLED" in request(path + "/calendar.ics", raw=True)
    for user in [owner, buyer, scanner, admin]:
        request("/auth/logout", data={"refresh_token": user["refresh_token"]}, expected=204)
    print(
        "PASS: login, event, activation, campaign PNG/link, promo, checkout, payment failure/retry, ticket PDF, support, check-in, duplicate/campaign rejection, analytics, suspension, refund, cancellation/calendar, logout."
    )
    print("Rehearsal event:", event["id"])
    print("Physical camera/printed-ticket scanning remains a manual acceptance check.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173")
    run(parser.parse_args().base_url)
