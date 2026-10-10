# Backend implementation status

M2, M3, M4, and M5 are implemented in the working tree. Merge/remote CI acceptance is
still pending; this records implementation progress rather than marking the
attached plan's “merged, tested, OpenAPI regenerated” checklist complete.

| Task | Delivered behavior |
|---|---|
| M2.1 | Four translated categories; predefined venue with two price categories, one section, two rows, and 20 seats |
| M2.2 | Draft CRUD/preview, publish/unpublish/cancel, stable generated slugs, audit records |
| M2.3 | Public browse/search by category/date/city/text; published unlisted detail; private events hidden |
| M2.4 | Ticket-type create/edit/hide, KZT pricing, windows/limits, inventory/capacity constraints and audits |
| M2.5 | Paid ticket types can be configured before activation; checkout enforcement is M4 |
| M2.6 | Local validated image uploads, cover management, authorized file access |
| M2.7 | Owner assigns/revokes event_admin, support_agent, co_organizer by email |
| M2.8 | My events with time/status classification; scanner's assigned events |
| M2.9 | New-draft duplication with fresh identifiers and reset inventory; campaigns/purchase data excluded |
| M3.1 | Campaign CRUD, discount/windows/limits/applicability, draft → active → disabled, audits |
| M3.2 | Generated/custom globally unique CITEXT promo codes |
| M3.3 | bfc_ token, web target URL, Segno PNG with distinct colors and PROMO label |
| M3.4 | Public link resolver returns event slug and exact promo; atomic successful-scan counter |
| M3.5 | Read-only cart discount preview and stable error codes |
| M3.6 | Pure whole-tenge discount function; percent floors, fixed caps, ticket applicability |
| M4.1 | Order/item/attendee/payment/ticket/redemption models and platform settings/seat-hold mappings |
| M4.2 | Verified checkout, windows/limits/activation gates, atomic inventory/promo holds, server-calculated fees/totals/expiry |
| M4.3 | Zero-total orders complete and issue tickets/queue notifications in one transaction |
| M4.4 | Simulated paid flow, one live attempt, failure retries, idempotent final callbacks |
| M4.5 | Standalone/Compose expiry worker plus lazy expiry; release inventory/seat holds/promo claims |
| M4.6 | Attendee tickets with short codes, bft_ tokens, seat snapshots, reserved → sold inventory |
| M4.7 | Buyer-only order/ticket lists and detail, protected ticket QR PNG |
| M4.8 | Last-ticket and last-promo-claim races; concurrent callback and expiry verification |
| M5.1 | Owner-only checklist: paid type, identity, active payout, fee, terms and eligibility |
| M5.2 | Fee settings/snapshots, zero-fee path, retries and idempotent simulated payments; terms acceptance |
| M5.3 | Transactional per-event activation, identity/payout revalidation, one-time fee and audit |
| M5.4 | Admin event/paid-sales suspension and restoration; checkout/callback/public-access gates; audited race tests |


The [events/campaigns guide](api-m2-m3.md), [checkout guide](api-m4.md) and
[activation/moderation guide](api-m5.md) document
routes, request examples, and lifecycle behavior.
`docs/openapi.json` is regenerated. Local checks use Python 3.12 and the installed
PostgreSQL 14; the existing CI configuration targets PostgreSQL 16.
Verification: **352 tests passed**, Ruff lint and format checks passed, and the
M2–M5 migrations passed upgrade/downgrade/upgrade checks. M5 needs no new
dependencies. CI also checks for OpenAPI drift.

## Decisions

- Draft deletion is soft deletion (`events.deleted_at`) to preserve immutable
  audit records. Deleted drafts are hidden from reads and authorization.
- An event must have a visible ticket type with positive inventory to publish.
- Allocated ticket inventory cannot exceed an explicit event capacity.
- Cancelled events and disabled campaigns are terminal. Cancellation of events
  with orders is blocked until M7 implements refunds/ticket/notification cascades.
- A QR stores its exact promo code reference; additional codes do not change it.
- QR links count successful resolutions and reject inaccessible events or
  unusable promotions. The web route consuming the link belongs to frontend integration.
- Preview has no side effects and excludes processing fees. M4 implements transactional
  reservations, checkout windows, paid-sales enforcement, and redemption claims.
- Positive-discount orders claim a redemption before payment, then confirm it on
  completion or release it on expiry. Existing order prices/discounts remain snapshots.
- Processing fees round down on the post-discount subtotal.
- Payment callback replays preserve the first final outcome and issue tickets once.
- B1 will create seat holds; M4 validates and attaches existing holds and preserves seat labels.
- Activation belongs to the verified event owner; co-organizers cannot accept paid terms or pay on their behalf.
- Activation fees are snapshotted at the first terms/payment mutation. Repeated activation never charges again.
- Event suspension preserves publication state and stops free and paid sales. Paid-sales suspension permits free registration. Admins restore each independently.
- Restoring previously activated paid sales revalidates the checklist; pending events cannot become active through unsuspension.
- The campaign-to-ticket integration flow now completes activation through public APIs.

**Next milestone: M6 — ticket PDFs and check-in API.**
