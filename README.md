# BiletFlow

Event ticketing MVP with a React/Vite web frontend and a FastAPI/PostgreSQL
backend. The backend uses asynchronous SQLAlchemy models over versioned SQL
migrations, JWT authentication, and an immutable audit trail. PostgreSQL keeps
inventory constraints and promo-code uniqueness consistent across requests.

## Development setup

```sh
cp .env.example .env
docker compose up -d db mailpit
docker compose run --rm migrate up
docker compose up -d api order-expiry
docker compose exec api uv run python -m app.scripts.seed_demo
```

API docs: <http://localhost:8000/docs>. Mailpit: <http://localhost:8025>.
The seed script creates demo accounts for admin, organizer, attendee, and
scanner roles. It prints their credentials and is safe to rerun. Migrations
seed translated event categories and a demo venue with sections, rows, seats,
and price categories. Organizer/staff assignment APIs connect users to events.

For the web frontend:

```sh
npm ci
npm run dev
```

The frontend currently contains an initial home page and navbar.

## Backend development and checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload
```

The default database URL uses the Docker PostgreSQL port. The pytest harness
creates and resets the separate `biletflow_test` database, so the configured
PostgreSQL user must be allowed to create databases. Run:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m app.scripts.export_openapi
```

CI runs the backend suite against PostgreSQL 16. Frontend checks are
`npm run lint` and `npm run build`.

## Current backend scope

M0/M1 foundations and user management are present. M2 adds events, venues,
ticket types, staff, images, and duplication. M3 adds campaigns, promo codes,
labeled campaign QR images, link resolution, and discount previews.
M4 adds checkout, atomic inventory/promo reservations, simulated payments,
expiry cleanup, ticket issuance, and buyer order/ticket/QR endpoints.
M5 adds per-event activation checklists, terms, simulated activation-fee
payments, activation, and admin event/paid-sales suspension controls.
PDF/check-in is M6; refund/support flows are M7.

See the [M2/M3 integration guide](docs/api-m2-m3.md),
[M4 checkout guide](docs/api-m4.md),
[M5 activation/moderation guide](docs/api-m5.md),
[implementation status](docs/milestones.md), [ERD](docs/erd.md), and
[generated OpenAPI contract](docs/openapi.json).
