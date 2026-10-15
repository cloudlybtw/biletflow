# Events and campaigns integration (M2–M3)

All paths below use `/api/v1`. Management calls send
`Authorization: Bearer <access_token>` from `/auth/login`.
The generated contract is [`openapi.json`](openapi.json); interactive docs are at `/docs`.

## Events (M2)

| Operation | Endpoint | Access |
|---|---|---|
| Categories (kk/ru/en) | `GET /event-categories` | Public |
| Venues and seating layout | `GET /venues`, `GET /venues/{venue_id}` | Public |
| Browse/search | `GET /events` | Published + public only |
| Event by slug | `GET /events/by-slug/{slug}` | Published public/unlisted; private returns 404 |
| Create draft | `POST /events` | Verified organizer |
| My events | `GET /events/my` | Organizer |
| Assigned events | `GET /events/assigned` | Active event_admin assignments |
| Preview draft/event | `GET /events/{event_id}` | Owner or assigned staff |
| Edit | `PATCH /events/{event_id}` | Owner/co_organizer |
| Publish/unpublish | `POST /events/{event_id}/publish`, `/unpublish` | Owner/co_organizer |
| Cancel | `POST /events/{event_id}/cancel` | Owner |
| Delete draft | `DELETE /events/{event_id}` | Owner; soft deletion retains audit trail |
| Duplicate | `POST /events/{event_id}/duplicate` | Owner |
| Ticket types | `GET /events/{event_id}/ticket-types` | Public for published public/unlisted; staff may see hidden types/drafts |
| Add/update ticket type | `POST /events/{event_id}/ticket-types`, `PATCH /events/{event_id}/ticket-types/{ticket_id}` | Owner/co_organizer |
| Staff list/add/revoke | `GET/POST /events/{event_id}/staff`, `DELETE /events/{event_id}/staff/{assignment_id}` | Owner |
| Images | `GET/POST /events/{event_id}/images` | Reading follows event visibility; writing requires owner/co_organizer |
| Edit/delete image | `PATCH/DELETE /events/{event_id}/images/{image_id}` | Owner/co_organizer |
| Image file | `GET /events/{event_id}/images/{image_id}/file` | Reading follows event visibility |

Browse accepts `category_id`, `city`, `q`, `date_from` (inclusive), and `date_to`
(exclusive), plus `limit` (1–100) and `offset`. Date values require a timezone
offset. `q` is a literal case-insensitive substring, including `%` and `_`.
Lists return `{ "items": [...], "total": n }` except categories, ticket types,
images, and staff, which return arrays. Event responses include a derived
`classification`: `Upcoming`, `Active`, `Completed`, or `Cancelled`.

Create an event (save the returned `id` and `slug`):

```json
{
  "title": "Almaty Live",
  "description": "Demo concert",
  "venue_id": "20000000-0000-0000-0000-000000000001",
  "category_id": "10000000-0000-0000-0000-000000000001",
  "timezone": "Asia/Almaty",
  "starts_at": "2030-11-01T19:00:00+05:00",
  "ends_at": "2030-11-01T22:00:00+05:00",
  "capacity": 100,
  "visibility": "public"
}
```

Add at least one visible ticket type with nonzero quantity before publishing:

```json
{
  "name": "General admission",
  "price_amount": 3000,
  "quantity_total": 100,
  "min_per_order": 1,
  "max_per_order": 5
}
```

Amounts are whole KZT. Paid ticket types can be configured while paid sales are
`disabled`; M4 checkout must block sales until M5 activation makes them active.
Ticket administration locks the event and ticket row. Quantity cannot fall
below reserved + sold, and allocated inventory cannot exceed event capacity.
Changing price or capacity is audited. Hide a type by patching `is_hidden`.
Event slugs stay stable after edits. Cancelled events are terminal.

Duplication creates a new draft with a new slug and calendar UID, copies editable
event fields and ticket types, resets inventory counters and paid-sales status,
and excludes campaigns, images, staff, orders, payments, tickets, check-ins, and
support cases. Images/staff can be configured independently on the new event.

Add staff using `{ "email": "user@example.com", "role": "event_admin" }`.
Roles are `event_admin`, `support_agent`, and `co_organizer`. The account must
exist and be active. Revocation takes effect on the next API request.

Upload images with multipart fields `file`, `is_cover`, and `alt_text`. PNG,
JPEG, and WebP are decoded and normalized to PNG without source metadata.
Default limits: 5 MiB input and 16 megapixels. Files use generated names under
`MEDIA_ROOT` (default `backend/media`; `/app/media` in Docker) and persist in the
development bind mount. One image per event may be the cover. Private/draft
files require the Bearer header; the frontend must fetch them with authorization
and display the resulting blob URL. Public files can be loaded directly.

Cancellation handles events with no orders. Events with orders return
`EVENT_CANCELLATION_REQUIRES_REFUNDS`; the transactional ticket/refund/
notification cascade belongs to M7. Draft deletion retains its database row and
immutable audit records but removes it from reads and permission checks.

## Campaigns (M3)

Campaign management requires the event owner or an active `co_organizer`.

| Operation | Endpoint |
|---|---|
| List/create | `GET/POST /events/{event_id}/campaigns` |
| Read/update/delete | `GET/PATCH/DELETE /events/{event_id}/campaigns/{campaign_id}` |
| Activate/disable | `POST /events/{event_id}/campaigns/{campaign_id}/activate`, `/disable` |
| Add promo code | `POST /events/{event_id}/campaigns/{campaign_id}/promo-codes` |
| Create/list QR records | `POST/GET /events/{event_id}/campaigns/{campaign_id}/qr` |
| Download PNG | `GET /events/{event_id}/campaigns/{campaign_id}/qr/{token}.png` |
| Resolve QR link | `GET /campaign-links/{token}` (public) |
| Discount preview | `POST /events/{event_id}/promo/validate` (public) |

Create a campaign:

```json
{
  "name": "Launch offer",
  "discount_type": "percent",
  "discount_value": 15,
  "max_redemptions": 100,
  "ticket_type_ids": [],
  "code": "LAUNCH15"
}
```

`code` is optional: omission generates a unique human-friendly `BF-` code.
Custom codes contain 3–40 ASCII letters/digits/underscores/hyphens, begin with a
letter or digit, and are stored uppercase. PostgreSQL CITEXT enforces global,
case-insensitive uniqueness. Creation returns `promo_codes` and creates a draft
campaign. Call `/activate` before public use. States follow
`draft → active → disabled`; disabled is terminal. Only unused drafts may be
deleted. Configurations and state changes are audited. `starts_at`, `ends_at`,
and `max_redemptions` can be null. A start time is inclusive; an end time is
exclusive. Limits cannot fall below recorded redemptions. Empty
`ticket_type_ids` means all ticket types; listed IDs must belong to this event.

Create a QR with `{}` to select the first active promo code, or
`{ "promo_code_id": "<uuid>" }` to select a specific code. The returned record
has `token` starting with `bfc_`, `target_url`, `image_url`, and label `PROMO`.
The downloadable PNG preserves Segno's quiet zone, uses navy modules, and has
an orange PROMO footer so it is distinct from a ticket. Each QR retains its
exact promo code even after other codes are added to the campaign.

`target_url` points to `${WEB_BASE_URL}/campaign-links/{token}`. The React app
must implement that page and call the backend resolver. Example response:

```json
{
  "event_slug": "almaty-live-<suffix>",
  "promo_code": "LAUNCH15",
  "campaign_id": "<uuid>"
}
```

Navigate to the event with that promo prefilled. The resolver accepts only
published public/unlisted events with currently usable promotions, and counts
successful scans atomically. It does not consume a redemption. Private, draft,
cancelled, deleted, unknown, and ticket-token links return 404.

Preview the cart:

```json
{
  "code": "launch15",
  "items": [{ "ticket_type_id": "<uuid>", "quantity": 2 }]
}
```

For two 3,000 KZT tickets, the response contains:

```json
{
  "campaign_id": "<uuid>",
  "promo_code_id": "<uuid>",
  "currency": "KZT",
  "subtotal_amount": 6000,
  "eligible_subtotal_amount": 6000,
  "discount_amount": 900,
  "total_amount": 5100
}
```

Percent discounts round down once on the eligible subtotal. Fixed discounts
are capped at that subtotal. Non-applicable types retain their full price.
Cart quantities must meet per-order limits; combine duplicate ticket IDs.
Preview checks that the event is publicly accessible and each type is visible;
it does not reserve inventory, claim a promo, enforce checkout windows, or
add processing fees. M4 must repeat event, ticket, inventory, paid-sales, and
promotion checks inside the checkout transaction, use `calculate_discount`, and
update redemption counters atomically.

Business errors use the existing `{ "error": { "code", "message", "details" } }`
envelope. Preview/link errors include `PROMO_EXPIRED`, `PROMO_DISABLED`,
`PROMO_EXHAUSTED`, `PROMO_NOT_APPLICABLE`, and `PROMO_NOT_STARTED`.

## Validation

Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`
from `backend/` with PostgreSQL available. Tests cover event lifecycle,
permissions, visibility/search, seed layout, uploads/covers, inventory races,
duplication exclusions, campaign transitions, custom-code uniqueness,
scoped/rounded/capped discounts, read-only previews, and concurrent QR scans.

After API edits run `uv run python -m app.scripts.export_openapi`.
The new migrations are `0004_event_catalog` and `0005_campaign_qr_promo_link`.
