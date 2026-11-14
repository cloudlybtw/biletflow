"""Reproducible local HTTP load: checkout alone vs checkout with analytics, plus QR latency."""

import argparse
import asyncio
import json
import math
import platform
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx

from app.scripts.seed_demo import DEMO_PASSWORD


def statistics(values):
    values = sorted(values)
    return {
        "requests": len(values),
        "p50_ms": round(values[math.ceil(len(values) * 0.5) - 1], 2),
        "p95_ms": round(values[math.ceil(len(values) * 0.95) - 1], 2),
        "max_ms": round(max(values), 2),
    }


async def run(base, buyers):
    if urlparse(base).hostname not in {"localhost", "127.0.0.1", "api", "web"}:
        raise ValueError("Load rehearsal is restricted to a local disposable deployment.")
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=100)
    async with httpx.AsyncClient(
        base_url=base.rstrip("/") + "/api/v1", limits=limits, timeout=60
    ) as client:

        async def request(method, path, token=None, data=None):
            start = time.perf_counter()
            response = await client.request(
                method,
                path,
                headers={"Authorization": "Bearer " + token} if token else {},
                json=data,
            )
            response.raise_for_status()
            return response.json(), (time.perf_counter() - start) * 1000

        tokens = []
        for email in ["organizer@example.com", "attendee@example.com"]:
            body, _ = await request(
                "POST", "/auth/login", data={"email": email, "password": DEMO_PASSWORD}
            )
            tokens.append(body["access_token"])
        owner, buyer = tokens
        start = datetime.now(UTC) + timedelta(days=14)
        event, _ = await request(
            "POST",
            "/events",
            owner,
            {
                "title": "Load rehearsal " + datetime.now(UTC).isoformat(),
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(hours=2)).isoformat(),
            },
        )
        path = "/events/" + event["id"]
        ticket, _ = await request(
            "POST",
            path + "/ticket-types",
            owner,
            {"name": "Load free", "price_amount": 0, "quantity_total": buyers * 2},
        )
        await request("POST", path + "/publish", owner)
        cart = {"items": [{"ticket_type_id": ticket["id"], "quantity": 1}]}
        orders = []

        async def checkout():
            body, elapsed = await request("POST", path + "/orders", buyer, cart)
            if body["status"] != "completed":
                raise AssertionError("Free checkout did not complete")
            orders.append(body)
            return elapsed

        # Same concurrency and dataset for both runs. No absolute throughput SLA invented.
        baseline = await asyncio.gather(*(checkout() for _ in range(buyers)))

        async def reports():
            values = []
            for _ in range(20):
                _, elapsed = await request("GET", path + "/analytics/summary", owner)
                values.append(elapsed)
            return values

        result = await asyncio.gather(reports(), *(checkout() for _ in range(buyers)))
        analytics, mixed = result[0], result[1:]
        scan = []
        for order in orders[:20]:
            detail, _ = await request("GET", "/orders/" + order["id"], buyer)
            issued, _ = await request("GET", "/tickets/" + detail["ticket_ids"][0], buyer)
            checked, elapsed = await request(
                "POST",
                "/checkin/scan?event_id=" + event["id"],
                owner,
                {"token": issued["qr_token"]},
            )
            if checked["result"] != "valid":
                raise AssertionError("QR check-in failed")
            scan.append(elapsed)
        summary, _ = await request("GET", path + "/analytics/summary", owner)
        if summary["sold"] != buyers * 2 or summary["reserved"] != 0:
            raise AssertionError("Inventory does not match successful orders")
        return {
            "recorded_at": datetime.now(UTC).isoformat(),
            "environment": {
                "platform": platform.platform(),
                "transport": "local HTTP; seeded demo accounts",
                "concurrent_checkouts": buyers,
                "buyer_sessions": 1,
                "analytics_requests": 20,
            },
            "baseline_checkout": statistics(baseline),
            "checkout_with_analytics": statistics(mixed),
            "analytics": statistics(analytics),
            "online_qr": statistics(scan),
            "qr_under_two_seconds": all(ms < 2000 for ms in scan),
            "mixed_to_baseline_p95_ratio": round(
                statistics(mixed)["p95_ms"] / statistics(baseline)["p95_ms"], 3
            ),
            "inventory_consistent": True,
            "limitations": [
                "One buyer session; distinct-buyer contention is covered by the regression suite.",
                "Local HTTP API timing excludes mobile camera, physical device and public-network latency.",
                "Small demo dataset; record production-sized measurements separately.",
                "Free checkout only; simulated paid checkout is covered by the HTTP functional rehearsal.",
            ],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--buyers", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.buyers <= 50:
        parser.error("--buyers must be between 1 and 50")
    print(json.dumps(asyncio.run(run(args.base_url, args.buyers)), indent=2))


if __name__ == "__main__":
    main()
