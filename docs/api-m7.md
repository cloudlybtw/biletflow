# Refunds, notifications, support, and private screenshots

All routes start with `/api/v1`. Send the access JWT as a bearer token. Money
and refunds are simulated; amounts are whole KZT. See `openapi.json` for schemas.

## Reversals

Owners/co-organizers use `POST /events/{event_id}/orders/{order_id}/cancel`
for free registrations, or `/refunds` for full paid-order refunds. Body:
`{"reason":"Requested by buyer"}`. Reversals atomically invalidate tickets,
return inventory, preserve retained order/payment history, queue notices, and
audit the action. Duplicate/concurrent reversals cannot return inventory twice.
`POST /events/{event_id}/cancel` cascades across purchases and unpaid holds,
simulates paid refunds, queues cancellation notices, and increments calendar
sequence. Cancellation is terminal; the web asks for confirmation.

## Inbox and email

`GET /notifications` is the current user's paginated in-app inbox;
`POST /notifications/{id}/read` marks an owned notification read. These are not
arbitrary email-outbox reads. The API lifespan's worker expires reservations and
delivers queued email every 30 seconds. A one-off pass is:

```sh
uv run python -m app.jobs.expire_orders --once
```

Mailpit captures local SMTP at port 1025; its web UI defaults to 8025. Templates
use the plan's permitted English fallback for kk/ru locales. Ticket delivery
attaches PDFs. Delivery failure retains a failed outbox row; an operator must
investigate/retry explicitly. SMTP acceptance and a database commit are not
atomic, so crash recovery can redeliver; stable Message-ID helps identify it.

## Support workflow

- `POST /support/cases`: attendee cases require an event/order/ticket context;
  organizer platform cases use `case_type=organizer` with optional owned event.
- Fields: `subject`, `body`, `category`, context IDs. Categories: ticket_delivery,
  payment, refund, seating, event_information, check_in, account, technical.
- `GET /support/cases`: my cases; `/events/{id}/support/cases`: event staff inbox;
  `/admin/support/cases`: platform inbox. Lists use items/total and limit/offset.
- `GET /support/cases/{id}` and `/messages`: authorized thread. `since` is an
  inclusive timezone-aware timestamp, so deduplicate polled messages by ID.
- `POST /support/cases/{id}/messages`: `body`, optional `is_internal_note`.
- `PATCH .../status`: `open`, `in_progress`, `waiting_for_customer`, `resolved`.
- `PATCH .../assignment`: `assigned_to_user_id` (null unassigns).

Requesters only see their cases. Event owner/co-organizer/support staff see
attendee cases for their event. Platform admins handle organizer cases. Internal
notes and their screenshots stay staff-only. Scanner role alone grants no
support access. The web polls messages and cases and displays server failures.

## Screenshot attachments (B3)

After posting a message, its author may upload a screenshot with multipart
`file` to `POST /support/cases/{case_id}/messages/{message_id}/attachments`.
PNG/JPEG/WebP are decoded, bounded to 16 megapixels, normalized to PNG, and capped
at `IMAGE_MAX_BYTES` before and after normalization. Maximum five per message.
Other formats are rejected. Upload failure leaves the posted message intact and
the web tells the user that only the screenshot failed.

`GET /support/cases/{id}/attachments` lists visible attachments;
`GET /support/cases/{id}/attachments/{attachment_id}` downloads an authorized
attachment. Storage uses UUID filenames under `MEDIA_ROOT/support-attachments`,
never client filenames or a public static mount. File responses are private,
no-store, nosniff downloads. Revoked staff and unrelated users cannot fetch them.
