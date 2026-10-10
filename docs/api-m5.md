# M5: paid-sales activation and moderation

All paths use `/api/v1`. Identity, payouts and all payments are clearly labelled
simulations: no real money moves.

## Organizer activation

Only the event owner, signed in with a verified email, can use these routes.
Co-organizers, scanners, support staff, other organizers and platform admins
cannot accept terms or pay on the owner's behalf.

| Method | Path | Purpose |
|---|---|---|
| GET | `/events/{id}/paid-sales/checklist` | Read requirements without creating records |
| POST | `/events/{id}/paid-sales/terms` | Accept terms with `{"accepted": true}` |
| POST | `/events/{id}/paid-sales/pay` | Create or reuse an activation-fee payment |
| POST | `/payments/{payment_id}/simulate` | Complete the owner's payment with `{"outcome": "success"}` or `"failure"` |
| POST | `/events/{id}/paid-sales/activate` | Revalidate requirements and enable this event's paid sales |

The checklist reports `has_paid_ticket_type`, `identity_verified`,
`payout_account_active`, `fee_paid`, `terms_accepted`, and `ready_to_activate`.
It includes the KZT fee, payment/activation IDs, payout account ID, terms and
activation timestamps, event suspension flag, and paid-sales suspension details
when an activation exists. `is_simulated` is always true.

Suggested flow:

1. Create a draft event and a visible positive-price ticket type.
2. `POST /organizers/me/identity-verification` to simulate identity verification.
3. `POST /organizers/me/payout-accounts` with `account_holder_name` and
   `external_account_ref` to register an active simulated KZT account.
4. Fetch the checklist and present the paid-event terms to the owner.
5. Accept terms, start the fee payment, then simulate success.
6. Activate with `{}` to choose an active account (default preferred), or with
   `{"payout_account_id": "<uuid>"}` to select an account belonging to the owner.
7. Publish the event and use M4 checkout.

Activation can happen before or after publication. Cancelled, deleted, ended
or suspended events cannot activate. Paid-sales suspension also blocks new
activation payments and unfinished activation-payment callbacks.

The first terms/payment mutation creates one activation per event and snapshots
`activation_fee_kzt` (seeded to 5000). It must be a non-negative whole KZT amount
fitting BIGINT. Invalid/missing settings return 503 `INVALID_ACTIVATION_SETTINGS`.
Later setting changes do not reprice this activation. A zero fee creates a
successful simulated payment immediately.

Fee success does **not** activate sales automatically. Activation requires a
visible positive-price ticket type, verified identity, an active simulated KZT
payout account belonging to the owner, accepted terms, and a successful matching
fee payment. Incomplete requirements return 409 `ACTIVATION_CHECKLIST_INCOMPLETE`,
with `details.missing` listing checklist keys. Original verification, terms and
activation timestamps are retained.

Repeated pay requests reuse an initiated or successful payment. Failed payments
may be retried with a new ID; previous attempts remain available in the database.
Repeated callbacks with the same final outcome have no additional effects;
changing an outcome returns `PAYMENT_ALREADY_PROCESSED`. Failure queues one
`payment_failed` notification per attempt; M7 delivers it. Activation can be
repeated without another fee. The selected payout account cannot change after
activation (`ACTIVATION_PAYOUT_LOCKED`).

## Platform moderation

Only authenticated, active platform admins may use these routes:

| Method | Path | Effect |
|---|---|---|
| POST | `/admin/events/{id}/suspend` | Suspend the entire event |
| POST | `/admin/events/{id}/unsuspend` | Remove event suspension |
| POST | `/admin/events/{id}/paid-sales/suspend` | Suspend only paid sales |
| POST | `/admin/events/{id}/paid-sales/unsuspend` | Restore prior activation eligibility |

Suspension requires `{"reason": "Suspicious activity"}`: a non-blank reason up
to 1000 characters. Unsuspension needs no body. Repeating the same state is a
no-op. Cancelled/deleted events cannot be restored by these endpoints.

Event suspension uses a separate `is_suspended` flag, preserving publication
status. It blocks free/paid orders, unfinished ticket/activation payment
completion, activation and organizer event/inventory edits. Public browse,
detail, ticket-type/image access and campaign links/promo validation hide the
event. Authorized staff may still preview retained records. Existing buyers
retain order/ticket access. Suspension does not cancel/refund completed orders;
pending reservations retain their expiry and are released by the M4 worker.

Paid-sales suspension blocks positive-price types, including those discounted
to zero, and payment completion for existing paid orders. Free registrations
remain possible unless the event is also suspended. Owners cannot bypass
suspension through activation or republication.

Restoring paid sales revalidates identity, payout, terms, fee and paid-ticket-type
requirements, retaining the original fee and activation timestamp. An event
never activated returns to `pending` or `disabled`; unsuspension cannot activate
an unpaid event. The two suspensions are independent. A paid-sales suspension
before activation is retained on the event, with its reason in the audit trail.

## Transactions and audit

Activation, moderation, checkout and callbacks serialize on the same event row.
After suspension commits, subsequent checkouts/callbacks cannot pass their sales
checks. A concurrent purchase may finish before suspension obtains the lock;
it then remains a valid prior purchase.

The database enforces one activation per event and at most one initiated or
successful activation payment per activation. State changes append audit entries
with actor, event, entity, timestamp and simulation/suspension details in the
same transaction. Audit/validation failure rolls back the change. Migration:
`0007_activation_moderation`.

The API integration test now covers event creation, campaign QR resolution,
promo validation, identity/payout setup, terms, fee payment, activation, ticket
checkout/payment and QR issuance without SQL activation. M6 adds PDF/check-in;
M7 adds notification delivery/refunds/support; M8 adds admin search/settings,
reports and the activity timeline. Client screens remain part of integration.
