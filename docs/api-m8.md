# Analytics, retained history, and platform administration

All routes start with `/api/v1`, require bearer authentication and enforce event
or platform permissions. Lists use `items`, `total`, `limit` (max 100), `offset`.
The React client fetches every page; exports enforce a 10,000-row bound.

## Organizer reporting

Under `/events/{event_id}/analytics`:

| Path                  | Contents                                                                                    |
| --------------------- | ------------------------------------------------------------------------------------------- |
| `/summary`            | Current capacity, sold/reserved/remaining, sales, discounts, fees, refunds, net, attendance |
| `/sales/daily`        | Daily sales in UTC buckets                                                                  |
| `/sales/ticket-types` | Sales by ticket type                                                                        |
| `/campaigns`          | Completed-order redemptions and campaign revenue                                            |
| `/promo-codes`        | Promo code revenue and redemptions                                                          |
| `/attendance`         | Registered, checked in, absent, percentage                                                  |

Add `.csv` to any path to export. Filters: timezone-aware `date_from`, `date_to`,
optional `ticket_type_id`. Financial values are whole KZT, explicitly simulated.
Inventory is current; date-filtered financial/attendance cohorts use orders in
the range. Historical order prices/discounts are snapshots. Activation fees are
excluded from ticket revenue. Refund measures are labeled independently from
completed-order campaign revenue. See response schema descriptions for scope.
Queries are read-only; tests verify they finish while checkout rows are locked
and that a representative sales query uses `ix_orders_event_placed`.

## History and operations

Under `/events/{id}`:

- `/history`: immutable activity, date range and `action_type` filters.
- `/orders`, `/orders/{id}`: retained buyer/order/payment state.
- `/tickets`, `/tickets/{id}`: attendee and ticket status without admission tokens.
- `/refunds`: retained simulated refunds.
- `/checkin/records`: retained scan/reversal results without scanned tokens.

## Platform administration

`GET /admin/{resource}` and `/admin/{resource}/{id}` support users, events,
orders, payments, refunds, activations. Filter with `q`, `status`, date range,
`event_id`; payments also accept `purpose=ticket_purchase|activation_fee`.
`/admin/{resource}/export.csv` uses the same filters and protects spreadsheet
formula prefixes. Exports require authorization and are never public links.

`POST /admin/users/{id}/suspend` and `/admin/events/{id}/suspend` require
`{"reason":"..."}`; `/unsuspend` restores access. Event `/paid-sales/suspend`
and `/paid-sales/unsuspend` control paid sales independently. Suspension blocks
new actions immediately; restoring paid sales revalidates prerequisites.

`GET /admin/settings` returns a list of key/value records. `PATCH` accepts one
or more typed numeric settings: activation_fee_kzt, processing_fee_percent,
order_hold_minutes, seat_hold_minutes. Updates validate and commit atomically.
The admin UI uses named controls, not a raw settings/JSON editor.
