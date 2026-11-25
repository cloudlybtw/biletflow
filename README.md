# BiletFlow

Live demo · **[biletflow-demo.vercel.app](https://biletflow-demo.vercel.app/)**

BiletFlow is a self-service event ticketing platform for Kazakhstan. Organizers
publish venue-based events, offer free registration or paid tickets in
Kazakhstani tenge (KZT), and assign staff to check attendees in with the
BiletFlow Verify mobile app. The customer-facing web app supports Kazakh,
Russian, and English.

Free registration carries no platform fee. Paid sales are activated per event
after the organizer completes simulated identity verification, configures a
payout account, accepts the paid-event terms, and pays a simulated one-time
activation fee. The academic MVP simulates payments, refunds, and payouts.

## What you can do

| Role | Workflow |
| --- | --- |
| Attendee | Discover events, register for free or complete simulated checkout, redeem promo codes, review orders, and access QR tickets by email or in your account. Download a print-ready PDF or open a support case linked to an event, order, or ticket. |
| Organizer | Create, preview, publish, and cancel events. Manage ticket types, sales windows, inventory, staff, campaigns, support cases, free-registration cancellations, and full simulated refunds. Review sales, campaign performance, attendance, and past events, then reuse event configuration in a new draft. |
| Event Admin | Use BiletFlow Verify on iOS or Android to open an assigned event, scan tickets online, search attendees, reverse a check-in when authorized, and view attendance counts. The API prevents duplicate admission and rejects Campaign QR codes at check-in. |
| Platform Admin | Search operational records, review reported events and escalated support cases, suspend users, events, or paid sales, and manage activation fees and platform settings. |

Campaign QR codes open an event page with the associated promo code. The API
validates eligibility, applies percentage or fixed-KZT discounts, and attributes
completed orders to the campaign.

The checkout API reserves inventory and promo redemptions atomically. Temporary
reservations expire, and paid tickets are issued after successful payment
confirmation. Sales reports use the platform's order, ticket, refund, campaign,
and check-in records. Each event has a chronological audit timeline.

### Implemented SRS extensions

- **Assigned seating** includes an interactive map for a seeded venue layout,
  accessible-seat indicators, per-category prices, blocked seats, and expiring
  checkout holds.
- **Calendar export** includes an `.ics` download and links for Google Calendar
  and Outlook. Calendar files retain a stable UID and reflect cancellations.
- **Support attachments** allow screenshots in private, asynchronous case
  threads.

The SRS defines online check-in for the MVP. Production identity verification
and financial processing, offline scanner synchronization, and app-store
publication are deferred.

## Run locally

Use Docker with Compose for PostgreSQL, the API, and Mailpit. Use Node.js 24
and npm for the Vite development server.

On a fresh checkout, use [the environment example](.env.example) to create
`.env`. Run the setup commands from the repository root.

```sh
cp .env.example .env
docker compose up -d db mailpit
docker compose run --rm migrate up
docker compose up -d api
docker compose exec api uv run python -m app.scripts.seed_demo
```

Start the web app in a separate terminal with npm.

```sh
npm ci
npm run dev
```

| Service | Default local URL |
| --- | --- |
| Web app | <http://localhost:5173> |
| Interactive API docs | <http://localhost:8000/docs> |
| OpenAPI schema | <http://localhost:8000/openapi.json> |
| Mailpit inbox | <http://localhost:8025> |

Vite proxies `/api` to port 8000. To use a different API origin, set
`VITE_API_BASE_URL` to the full API base URL ending in `/api/v1`. Set
`WEB_BASE_URL` to the web origin used for email and campaign links.

To serve the built web app through Nginx, use
`docker compose up --build -d web` in place of the Vite server. The Compose web
service uses port 5173 by default and proxies `/api/` to the API container.

## Try the demo

The seed script prints sign-in credentials for the four roles and can be rerun.
It creates free and paid demo events, a promotion, sample orders, support cases,
and staff assignments.

1. Sign in as the organizer, open **Almaty Live Demo**, and copy the campaign
   link or download its Campaign QR code.
2. Sign in as the attendee in a separate browser profile. Open the link, confirm
   the discount at checkout, simulate a successful payment, and download the PDF
   from **My tickets**. Check Mailpit for the ticket email.
3. Open a support case from the ticket and reply from the organizer workspace.
4. Run [BiletFlow Verify](mobile/README.md), sign in as the Event Admin, and open
   the assigned event. Scan the newly issued ticket twice to check admission and
   duplicate rejection, then scan the Campaign QR to check that it is rejected.
5. Review campaign and attendance reports as the organizer. As the Platform
   Admin, suspend the event and confirm that it stops accepting orders.

Run the automated rehearsal against a disposable seeded local instance.

```sh
docker compose exec api uv run python -m app.scripts.rehearse_demo --base-url http://localhost:8000
```

The rehearsal creates and cancels a demo event through the API. Use a physical
phone and a printed ticket to verify camera and paper scanning.

## Development and checks

| Component | Stack and source |
| --- | --- |
| Web | React, Vite, Tailwind CSS in [`src/`](src/) |
| API and database | FastAPI, async SQLAlchemy, PostgreSQL 16, and [versioned SQL migrations](backend/migrations/) in [`backend/`](backend/) |
| Check-in app | Flutter and Dart in [`mobile/`](mobile/) |
| Local services | [Docker Compose](docker-compose.yml), Nginx, and Mailpit |

Run the web checks from the repository root.

```sh
npm run lint
npm test
npm run build
```

For local backend development, keep PostgreSQL and Mailpit running through
Compose. Install Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/), then use
`uv run uvicorn app.main:app --reload` from `backend/` in place of the Compose
API service. The backend reads the root `.env` when started from `backend/`.

```sh
cd backend
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The test harness creates and resets a separate `biletflow_test` PostgreSQL
database. The configured database user needs permission to create databases.

[CI](.github/workflows/ci.yml) runs the web and backend checks and builds the
Flutter app for Android and the iOS simulator. See the
[mobile setup and checks](mobile/README.md) for code generation and the API
address to use on an emulator, simulator, or physical device.

Production configuration is illustrated in the
[production environment example](deploy/production.env.example). The repository
also provides a [database and media backup utility](backend/app/scripts/backup.py)
and a [daily backup timer](deploy/systemd/biletflow-backup.timer).
