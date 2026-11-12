# Ticket PDFs and Flutter check-in contract

The committed `openapi.json` is authoritative. All paths below start with
`/api/v1`. Protected requests use `Authorization: Bearer <access_token>`.

## Authentication

`POST /auth/login` accepts `{ "email": "…", "password": "…" }` and returns
`access_token`, `refresh_token`, `expires_in`, and `user`. Store tokens securely
on the device. `GET /me` restores the user. On a 401, exchange the refresh token
once at `POST /auth/refresh` with `{ "refresh_token": "…" }`; save **both** new
tokens, then retry the original request once. `POST /auth/logout` with the
current refresh token revokes it; always clear device tokens on sign-out.

## Assigned events and PDF

- `GET /events/assigned`: events assigned to the signed-in scanner. Lists use
  `{ "items": [...], "total": 123 }` and `limit` (1–100), `offset`; fetch later
  pages instead of silently hiding assignments.
- `GET /tickets/{ticket_id}/pdf`: buyer-authorized A4 PDF, generated on demand.
  QR contains the same `bft_` token as the digital ticket. Dates use the event's
  timezone; the PDF includes attendee, ticket type, venue, and any seat labels.

## Four check-in operations

Owners and active `event_admin`/`co_organizer` staff may admit and reverse.
Reading counters/search also permits platform admins. Staff of another event
receive no access. The event ID for a scan is a **query parameter**.

| Operation        | Request                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------- |
| QR scan          | `POST /checkin/scan?event_id={id}` with `{ "token": "bft_…" }`                                |
| Manual admission | Same scan endpoint with `{ "ticket_id": "uuid" }`                                             |
| Search           | `GET /events/{id}/checkin/attendees?q=Dana&limit=100&offset=0`                                |
| Undo             | `POST /events/{id}/checkin/records/{record_id}/reverse` with `{ "notes": "Accidental scan" }` |

Send exactly one of `token` and `ticket_id`; optional `device_id` identifies the
scanner. A successful scan request returns HTTP 201 **even for a denied verdict**:

```json
{
  "record_id": "uuid",
  "event_id": "uuid",
  "action": "check_in",
  "result": "valid",
  "source": "qr_scan",
  "scanned_at": "2026-11-12T10:00:00Z",
  "reverses_record_id": null,
  "ticket": {
    "ticket_id": "uuid",
    "ticket_code": "BF123",
    "attendee_name": "Dana",
    "attendee_email": "dana@example.com",
    "ticket_type_id": "uuid",
    "ticket_type_name": "General",
    "status": "checked_in",
    "checked_in_at": "2026-11-12T10:00:00Z",
    "seat_section_label": null,
    "seat_row_label": null,
    "seat_number_label": null,
    "check_in_record_id": "uuid"
  }
}
```

Other results are `duplicate`, `cancelled`, `refunded`, `invalid`, `wrong_event`,
and `campaign_code_rejected`. `ticket` can be null on rejections. Never infer
admission from HTTP status alone. Unknown verdicts, malformed responses, network
failures, and timeouts must not admit. Undo uses the successful response's
`record_id`, not a ticket ID or a later duplicate scan record.

`GET /events/{id}/checkin/counters` returns:

```json
{ "registered": 12, "checked_in": 3 }
```

Search items use `attendee_name`, `attendee_email`, `ticket_type_name`, and
`checked_in_at`. Error responses use
`{ "error": { "code": "FORBIDDEN", "message": "…", "details": {} } }`.

## Mobile verification

From `mobile/`, with Flutter 3.50.0 / Dart 3.14.0 (the CI toolchain):

```sh
flutter pub get
dart run build_runner build
flutter analyze --no-fatal-infos
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Use the host's LAN IP on a real phone. A camera/printed-ticket rehearsal on the
Docker deployment remains a deferred acceptance check; follow `docs/demo-flow.md`
when a device is available and record the device and results.

Flutter 3.50 reports existing Material imports as informational deprecations.
`--no-fatal-infos` preserves these diagnostics; analyzer errors and warnings
still fail CI. Migration to the new Material package is separate framework work.
