# Demo rehearsal and acceptance map

The automated rehearsal targets disposable local demo data. It never moves real
money or sends mail beyond the configured local SMTP capture service.

## Docker setup

Copy `.env.example` to `.env`, use `POSTGRES_DB=biletflow_demo`, set DATABASE_URL
to that database for host commands, and choose free host ports. For an initial
setup:

```sh
docker compose up -d db mailpit
docker compose run --rm migrate up
docker compose up --build -d api web
docker compose exec -T api uv run python -m app.scripts.seed_demo
```

The web defaults to port 5173; API 8000; Mailpit UI 8025. `.env` can override
WEB_PORT, API_PORT, POSTGRES_PORT and MAILPIT_WEB_PORT. Do not commit `.env`.
All four seeded accounts use `demo-pass-2026`:

| Account                | Role                                            |
| ---------------------- | ----------------------------------------------- |
| admin@example.com      | Platform admin                                  |
| organizer@example.com  | Verified organizer with active simulated payout |
| attendee@example.com   | Buyer of paid and free tickets                  |
| eventadmin@example.com | Assigned scanner for both demo events           |

Seed adds two events 14/15 days ahead, inventory, active DEMO15 promotion and QR,
completed paid/free orders, four tickets, two support conversations and two
check-ins. Reruns retain identifiers, existing transactions and history; they do
not reset an event that a teammate intentionally cancelled/refunded. Use reset
to refresh dates and get a clean demo.

## Explicit reset

Only a database whose exact name ends `_demo` is eligible. Stop the API worker
while resetting, then start it again. The command drops all data in that named
demo database, rebuilds migrations, restores golang-migrate's version marker,
and seeds it. It refuses the default `biletflow` database or wrong confirmation.

```sh
docker compose stop api
docker compose run --rm api uv run python -m app.scripts.reset_demo --confirm biletflow_demo
docker compose up -d api
```

## Automated rehearsal

Through the production web proxy:

```sh
docker compose exec -T api uv run python -m app.scripts.rehearse_demo --base-url http://web
docker compose exec -T api uv run python -m app.jobs.expire_orders --once
```

This signs in all roles, creates/publishes an event, activates paid sales,
creates and resolves a campaign QR, validates a promo, buys a ticket, retries a
failed payment, downloads the PDF, opens/replies to support, checks in via the
scanner identity, rejects duplicate and campaign scans, checks analytics,
suspends/restores sales, refunds, cancels, checks cancelled ICS, and logs out.
It asserts responses and exits nonzero on failure; it never prints access or
refresh tokens. Each run creates a separate rehearsal event and retains its
cancelled/refunded history. The seeded tickets remain available for the manual
camera demonstration. SMTP delivery is checked separately in Mailpit.

## Manual web/mobile rehearsal

1. In the web app, sign in as attendee and open My orders/My tickets. Download
   the **valid, not yet checked-in** seeded ticket's A4 PDF. Print it.
2. Sign in as organizer: inspect analytics, campaign QR, support, and staff.
3. Run Flutter with API_BASE_URL pointing to the API host's reachable LAN IP
   and configured API_PORT (Android emulator can use 10.0.2.2).
4. Sign in as eventadmin, choose the correct event, and scan the printed ticket:
   valid once, duplicate on a second scan. Confirm counts, search, and undo.
5. Scan the campaign QR: reject. Scan a ticket from the other event: wrong_event.
6. Refund/cancel via organizer and confirm admission is blocked; check Mailpit
   for ticket PDF, support, refund and cancellation email.

Physical camera/printing and a visual browser pass require the actual device
and browser host. Automated HTTP and DOM tests do not certify those steps.

## Acceptance map

This maps the supplied plan's SRS references to executable evidence. The complete
SRS document is not checked in; this is not a claim of additional unseen criteria.

| Plan / SRS area                                     | Evidence                                                                                     |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| M0 foundation                                       | tests/db, tests/core, tests/test_health.py; Compose migration rehearsal                      |
| M1 / 4.1 identity and roles                         | tests/auth, tests/users, tests/organizers, tests/core/test_deps.py                           |
| M2 / 4.2–4.3 events and inventory                   | tests/events/test_events.py, tests/orders/test_seats.py                                      |
| M3 / 4.14 promotions                                | tests/campaigns; tests/test_m2_m3_flow.py                                                    |
| M4 / 4.4, 4.6–4.7 checkout/payment/tickets          | tests/orders; 50-buyer contention cases                                                      |
| M5 / 4.5 activation and moderation                  | tests/activation; HTTP rehearsal suspension check                                            |
| M6 / 4.7–4.8 PDF/check-in                           | tests/checkin; mobile/test/api_contract_test.dart                                            |
| M7 / 4.9–4.10, 4.13 reversals/support/notifications | tests/refunds, tests/support, tests/notifications                                            |
| M8 / 4.12, 4.15–4.16 reports/admin/history          | tests/analytics, tests/admin, tests/history                                                  |
| M9 integration                                      | tests/client.test.js, tests/ui.test.js; Docker HTTP rehearsal; manual device checklist above |
| M10 hardening                                       | tests/core/test_http.py, reset guard, contention tests; security-and-testing.md              |
| B1 assigned seating                                 | tests/orders/test_seating_api.py and test_seats.py                                           |
| B2 / 4.11 calendar                                  | tests/events/test_calendar.py                                                                |
| B3 screenshot attachments                           | tests/support/test_attachments.py                                                            |
