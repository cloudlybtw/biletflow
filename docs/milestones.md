# Implementation status — 2026-11-13

The detailed work/verification ledger is [FIX_PLAN.md](../FIX_PLAN.md). The API
contract is [openapi.json](openapi.json). Implementation is published in
[draft PR #6](https://github.com/cloudlybtw/biletflow/pull/6), which records remote
CI checks. The remaining hardware/access acceptance is listed below.

| Milestone | Current implementation                                                                                                                        |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| M0        | uv/FastAPI skeleton, PostgreSQL migrations, Docker, ERD, health/error envelope, async fixtures, CI and schema export                          |
| M1        | Auth/verification/reset/rotation/logout, roles, profiles, simulated identity/payout and demo accounts                                         |
| M2        | Events/search/visibility, inventory/images, staff/classification and duplication                                                              |
| M3        | Campaign lifecycle, codes, labeled promo QR/link resolution, pure discounts and previews                                                      |
| M4        | Atomic inventory/promo reservation, free/paid checkout, simulated payment retries, expiry and tickets                                         |
| M5        | Per-event paid-sales checklist/fee/terms/activation and independent event/paid-sales moderation                                               |
| M6        | A4 PDFs, QR/manual check-in, races/reversal/counters; Flutter auth and contract integration                                                   |
| M7        | Refund/cancellation cascades, SMTP outbox/PDF delivery, inbox and scoped support with staff notes                                             |
| M8        | Exact simulated reports, CSV, retained history, admin search/settings/suspension and query/index checks                                       |
| M9        | React workflows connected; rotating sessions and protected routes; realistic idempotent seed; Compose web proxy and executable HTTP rehearsal |
| M10       | Request limits/CORS/security headers, guarded demo reset, contention and regression checks, demo/acceptance documentation                     |
| B1        | Seat map, private holds/release, atomic seat race and checkout integration                                                                    |
| B2        | UTF-8 folded ICS, stable UID/sequence/cancellation state, Google/Outlook links                                                                |
| B3        | Private screenshot attachments with size/count/type validation and note visibility                                                            |

Native Chrome desktop and 390px visual acceptance is recorded in
[the review log](acceptance-2026-11-13.md). Remaining acceptance evidence: physical
Flutter camera/printed-ticket scan and the team's Jira triage board. The rate limiter is process-local; consult
[security and testing](security-and-testing.md) before multi-worker deployment.

Decisions retained: whole-tenge amounts; floor percentage/processing-fee rounding;
verified-account checkout; immutable audit records; terminal event cancellation;
snapshotted order prices; idempotent final payment outcomes; server-authoritative
admission. Bonus endpoints extend `/api/v1` additively.
