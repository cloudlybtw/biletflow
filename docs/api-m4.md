# Checkout, payments, and tickets (M4)

All endpoints use `/api/v1` and a Bearer access token. Creating orders, starting
payments, and simulating payment outcomes require a signed-in, email-verified
account. Order/ticket reads require a signed-in account. Every order, payment,
and QR lookup checks that the acting account is the order buyer; naming someone
as an attendee does not grant that account purchase access.

| Operation | Endpoint |
|---|---|
| Checkout | `POST /events/{event_id}/orders` |
| My orders | `GET /orders?limit=20&offset=0` |
| Order detail | `GET /orders/{order_id}` |
| Start/reuse payment | `POST /orders/{order_id}/pay` |
| Finish simulated payment | `POST /payments/{payment_id}/simulate` |
| My purchased tickets | `GET /tickets?limit=20&offset=0` |
| Ticket detail | `GET /tickets/{ticket_id}` |
| Ticket QR PNG | `GET /tickets/{ticket_id}/qr.png` |

Lists return `{ "items": [...], "total": n }`. The exact request/response
schemas are in [`openapi.json`](openapi.json) and `/docs`.

## Checkout request

```json
{
  "promo_code": "LAUNCH15",
  "items": [
    {
      "ticket_type_id": "<uuid>",
      "quantity": 2,
      "attendees": [
        { "full_name": "Alice", "email": "alice@example.com" },
        { "full_name": "Bob", "email": "bob@example.com" }
      ]
    }
  ]
}
```

`promo_code` and `attendees` are optional. Omit `attendees` to use the buyer's
name/email/phone for every ticket. Otherwise supply exactly one attendee per
unit. Each ticket type appears once; combine quantities in that line. Requests
support up to 100 cart lines and 1,000 tickets total, subject to each type's own
per-order limits. Prices, discounts, fees, currency, and buyer identity come
from the server; clients cannot submit them.

Checkout validates:

- Event exists, is published, and has not ended or been deleted. Public and
  unlisted events are purchasable. Private events are restricted to their owner
  and active assigned staff until an invitation feature exists.
- Registration window and each ticket type's sales window. Start times are
  inclusive, end/close times exclusive; unset windows impose no extra limit.
- Visible ticket types belonging to the event, min/max per-order quantities,
  and remaining inventory.
- Any type with a positive price requires `paid_sales_status = active`, even
  when a promo reduces the eventual total to zero. See the [M5 guide](api-m5.md)
  for activation and moderation endpoints. Event suspension blocks free and
  paid checkout; there is no activation bypass.
- Promo state, window, limit, event association, and eligible types using M3's
  discount rules. Errors include `PROMO_DISABLED`, `PROMO_EXPIRED`,
  `PROMO_NOT_STARTED`, `PROMO_EXHAUSTED`, and `PROMO_NOT_APPLICABLE`.

The transaction locks the event, promo, ticket inventory, and any seat holds.
Administrative changes and purchases serialize on the event. Inventory is
reserved atomically; the schema also rejects overselling. A failed checkout
rolls back the order, attendees, reservations, promo claim, ticket issuance,
notifications, and audit records together.

Positive promo discounts claim one redemption at reservation time. The campaign
counter includes completed redemptions and unexpired pending claims, preventing
two buyers from claiming the last slot. A `promo_redemptions` record is written
only on completion. Expiry releases the pending claim; a percentage that rounds
to zero does not claim a redemption.

Amounts are whole KZT. Percent discounts floor the eligible subtotal; fixed
amounts are capped there. The order discount is apportioned across eligible
lines with largest-remainder allocation, preserving the order total and
preventing negative line totals. Processing fees floor
`(subtotal - discount) × processing_fee_percent / 100` and are added to the
buyer's total. Fees and the hold duration come from `platform_settings`;
defaults are 0% and 15 minutes. Hold minutes must be a whole number from 1 to
10,080 and the fee percentage must be finite and between 0 and 100. Invalid
configuration blocks checkout with `INVALID_CHECKOUT_SETTINGS`. Amounts that
cannot fit a PostgreSQL BIGINT return `CART_TOTAL_TOO_LARGE`.

The returned order stores immutable purchase-price/discount snapshots. Later
price or promo changes do not reprice an existing order. Repeated checkout POSTs
create distinct orders; clients should avoid submitting the same cart twice.

## Free and paid flows

When `total_amount = 0`, checkout returns `status = completed`, issues one ticket
per attendee, moves inventory from reserved to sold, records any redemption,
and queues order-confirmation and ticket-delivery emails in the same
transaction. No payment attempt is created.

A positive-total checkout returns `status = pending`, `expires_at`, populated
order items/attendees, and an empty `ticket_ids` list. To pay:

1. `POST /orders/{id}/pay` returns a payment with `status = initiated`,
   `provider = biletflow_sim`, `purpose = ticket_purchase`, and
   `is_simulated = true`. The order becomes `awaiting_payment`. Repeating `/pay`
   while that attempt is live returns the same payment ID.
2. `POST /payments/{id}/simulate` with `{ "outcome": "success" }` completes the
   order and issues tickets atomically. Fetch the order again for `ticket_ids`.
3. Use `{ "outcome": "failure" }` to mark the attempt failed and queue one
   payment-failed notification. The order keeps its inventory and promo claim
   until the original deadline. Calling `/pay` again creates a new attempt;
   retries never extend that deadline.

The same final outcome can be replayed without duplicate tickets, redemptions,
or notifications. Conflicting outcomes return `PAYMENT_ALREADY_PROCESSED`.
Only the order buyer can simulate a demo ticket payment. M5 extends this
endpoint to activation-fee payments owned by the event organizer. Real-provider
payments cannot use it. Nothing here charges a real payment account.

Payment initiation and completion recheck the locked order deadline and event
moderation state. Unpublished/cancelled/deleted/ended events and inactive paid
sales block new completion. Registration/sales windows are checked at checkout;
reserved prices and discounts are honored until the order deadline. Disabling
or editing a campaign after a claim does not revoke that existing discount.

## Expiry

The `order-expiry` Docker Compose service runs the worker every 60 seconds.
Start it after applying migrations:

```sh
docker compose up -d api order-expiry
```

Outside Docker, from `backend/`:

```sh
uv run python -m app.jobs.expire_orders --interval-seconds 60
# One batch, useful for a demo reset or operational check:
uv run python -m app.jobs.expire_orders --once
```

Each pass processes up to 100 expired orders, skips busy events, and rechecks
state under locks, so multiple workers are safe. Expiry changes payable orders
to `expired`, releases reserved inventory and positive promo claims, marks linked
active seat holds expired, and cancels initiated payment attempts. Repeated
passes have no further effect. Completed orders retain their tickets and sold
inventory, regardless of their original `expires_at` value.

Expiry also runs lazily on order reads, before payment actions, and before new
checkout for the same event. My-orders reads clean up a batch of that buyer's
expired reservations. Event checkout cleanup is committed before validating a
new cart, so stale reservations remain released even if that new cart is
invalid. A late payment cannot issue tickets and returns `ORDER_EXPIRED`.

## Assigned seats and ticket QR

M4 consumes existing seat holds for assigned events; the seat-map and hold
creation/release endpoints are the B1 bonus. Supply `seat_hold_ids` per cart
line, one hold per unit in the same order as `attendees`. Holds must be active,
unexpired, owned by the buyer, unclaimed, and match the event, venue, and ticket
type. Standalone holds protect seats; ticket-type inventory is reserved when
checkout attaches them. Their expiry is aligned to the order deadline.
General-admission checkout rejects seat holds. M4 does not create a seat-hold
API as a substitute for B1.

Completion converts attached holds and writes seat section/row/number snapshots
to tickets. Ticket codes are short `BF-` human-readable strings; QR tokens use
`bft_` with a random suffix. Ticket QR PNGs encode that raw token in black and
white, preserving the quiet zone. Campaign QR tokens retain their distinct
`bfc_` prefix and PROMO styling.

Ticket details include attendee, event/timezone, venue, ticket type, status, seat
labels, and `qr_image_url`. QR downloads require the buyer's Bearer header and
use `Cache-Control: private, no-store`; fetch the image as an authorized blob in
the web client. PDF generation and check-in are M6.

Confirmation/delivery/failure notification rows are queued in the outbox. The
SMTP sender and templates are M7; queueing does not imply an email was sent.

## Validation and migrations

M4 tests cover checkout permissions/windows/inventory, fee and discount math,
atomic rollback, free completion, retries and callback replays, last-ticket and
last-promo races, expiry and late success, seat hold attachment/release, and
buyer-only order/ticket/QR access. The API walkthrough now runs through M2/M3
campaign creation and QR resolution into checkout, payment, and ticket issuance.

Migration `0006_checkout_guards` adds one-live-ticket-payment-per-order and
one-ticket-per-attendee uniqueness guards. Apply with the normal migration
command before starting the API and worker. The backend suite checks the new
model columns/enums against the database and tests migration rollback/reapply.
