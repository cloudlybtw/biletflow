# BiletFlow integration and hardening fixes

Based on the PLAN.md audit on 2026-11-12. Backend M0–M8 behavior is implemented;
the remaining work is integration, reproducible demos, documentation, and hardening.
Keep the existing `/api/v1` backend contract authoritative. Work in the order below;
mark implementation and verification separately. Do not mark device/deployment
checks complete based only on source inspection. No deployment is implied.

## Ordered work

| ID  | Status                                                                | Scope and acceptance criteria                                                                                                                                                                                                                                                                                     |
| --- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F01 | Complete (local checks)                                               | Restore Flutter auth files; secure token persistence, session restoration, refresh, server logout. Align routes, request bodies, nested scan responses, result enums, counters, pagination, and error envelopes with OpenAPI. Add contract tests; run code generation, analyzer, and tests when SDK is available. |
| F02 | Complete (local checks)                                               | Fix all six frontend lint errors, including organizer orders crash. Keep lint/build green and add frontend checks to CI.                                                                                                                                                                                          |
| F03 | Complete (local checks)                                               | Shared React API/session layer: authenticated requests, refresh rotation, logout, protected role routes, useful loading/error/empty states, configurable CORS. Wire login/register/verification/password reset and profile settings.                                                                              |
| F04 | Complete (local checks)                                               | Live public event detail and campaign-link resolution, promo validation, checkout, simulated payment, buyer orders/tickets/PDF, inbox, and support workflows. Remove fake success messages and purchase data from product flows.                                                                                  |
| F05 | Complete (local checks)                                               | Live organizer event CRUD, ticket types, publish/cancel/duplicate, images, staff, paid-sales activation, campaigns/QR, orders/refunds, analytics, history, and support. Persist mutations through APIs; display server validation errors.                                                                         |
| F06 | Complete (local checks)                                               | Live admin user/event moderation, activation/payment/refund searches, support, settings, and CSV exports. Backend authorization remains authoritative.                                                                                                                                                            |
| F07 | Complete (local checks)                                               | Extend idempotent demo seed with future events, paid/free orders, campaign, support conversation, checked-in ticket, and scanner assignment. Test reruns and resulting relationships. Provide explicit reset/reseed command.                                                                                      |
| F08 | Complete (local checks)                                               | Restore M6/M7/M8 guides and demo-flow/SRS acceptance map. Update milestones and README to match implemented behavior and known limits. Document web/mobile auth and frozen contract.                                                                                                                              |
| F09 | Complete (local checks)                                               | Add configurable login/promo rate limits with regression tests, review permission coverage, secret handling and analytics/PII paths. Document process-local limiter limits for multi-worker deployment.                                                                                                           |
| F10 | Complete (local checks)                                               | Add 50-buyers/10-tickets contention check, assert no oversell and consistent inventory; retain existing concurrency/migration tests. Review business-rule coverage without inventing coverage percentages.                                                                                                        |
| F11 | Partial: automated Docker/SMTP passed; manual/external checks pending | Docker deployment rehearsal: migrate, seed, web login → campaign → checkout → PDF → support → physical Flutter scan → duplicate rejection → campaign rejection. Verify actual SMTP delivery. Record device/runtime and results; external Jira triage board requires connected project/access.                     |
| F12 | Complete (local checks)                                               | B1 seat-map/hold/release APIs, checkout UI and race tests; B2 ICS/Google/Outlook links with UID/sequence/cancellation; B3 private bounded screenshot uploads/downloads with internal-note access protection. Attachments support PNG/JPEG/WebP screenshots rather than arbitrary files.                           |

## Verification ledger

- Baseline: 685 backend tests passed on local PostgreSQL 14; backend Ruff checks
  passed; generated OpenAPI matches; CI passed on PostgreSQL 16.
- Baseline: frontend build passed; lint failed with six errors.
- Baseline: Flutter/Dart executables unavailable; source has missing auth imports
  and incompatible endpoints/DTOs. Runtime verification is outstanding.
- F01: restored auth source, secure storage/session/logout wiring, exact backend
  routes and DTOs, strict paginated lists, backend error envelopes, rejection-safe
  scan decoding, contract regression tests, and `docs/api-m6.md`. Temporary SDK
  installed under `/tmp` (Flutter 3.50.0, Dart 3.14.0). DTO code generation
  passed; **17 tests passed**. `flutter analyze --no-fatal-infos` passed with
  zero errors/warnings and 14 existing Material import deprecation infos.
  Lockfile updated only for three SDK-pinned transitive packages (`meta`,
  `test_api`, `vector_math`). Added a pinned mobile CI job; remote execution
  awaits push. Printed-ticket/camera/device acceptance remains F11.
- F02: `npm run lint` and `npm run build` passed. Split shared constants from
  React component exports. Removed the undefined organizer order fixture access;
  F05 now supplies live organizer order data. Added the `web` CI job (Node 24, npm ci,
  lint, production build). Remote execution awaits push.

### Pass 1 — live integration (completed 2026-11-13)

- F03: shared bearer client, one rotating refresh for concurrent 401s, session
  restoration/logout/suspension handling, per-tab sessionStorage, role gates,
  configurable CORS, auth/verification/reset/profile forms. Tests cover refresh
  races, rejected credentials, user restoration and logout.
- F04: server event discovery/detail and owner draft preview; campaign-link
  resolution/promo preview; checkout, retriable simulated payment (including
  reloaded `awaiting_payment` orders), buyer orders/tickets/QR/PDF, inbox/support.
  Removed fixture data and fake purchase/account success from product flows.
- F05: organizer event/ticket/image/staff CRUD, publication/cancellation/
  duplication, paid-sales activation, campaigns/codes/QR, retained orders,
  refunds, attendee/scan history, filters and financial reports/CSV, support.
- F06: real admin searches/detail/CSV, user/event/paid-sales moderation, platform
  settings, and scoped support. Server permissions remain authoritative.
- F07: idempotent demo scenarios (two future events, paid/free orders, four
  tickets, campaign, conversations and scanner assignments); rerun tests and
  guarded *_demo-only reset. Reset verified on the isolated Docker database;
  subsequent golang-migrate `up` reported `no change`.

### Pass 2 — hardening and verification (completed 2026-11-13)

- F08: restored M6/M7/M8 guides, acceptance map and executable demo walkthrough;
  updated README/milestones. Added security/testing guidance and bug template.
- F09: bounded process-local login/promo limits, 429 envelope/Retry-After,
  explicit CORS, no-store/nosniff/no-referrer, production Nginx CSP/proxy, guarded
  downloads and screenshot storage. No GA4/PII forwarding found in source.
  Compatible dependency fixes plus patched minimatch override: npm install's
  audit reported **0 vulnerabilities**. Multi-worker/proxy limiter constraints
  are documented, not represented as a distributed production limiter.
- F10: free and paid **50 buyers / 10 tickets** tests pass with exactly ten
  winners, no oversell, and consistent reservation/issuance counts. Business
  rules mapped to tests; no invented coverage percentage or throughput SLA.
- F11: Docker/PostgreSQL 16 + API + Nginx web + Mailpit built and started.
  `rehearse_demo --base-url http://web` passed login → event → activation →
  campaign → promo → checkout → failed payment/retry → PDF → support → check-in
  → duplicate/campaign rejection → analytics → suspension → refund → event
  cancellation/automatic refund → cancelled ICS → logout. Mailpit captured
  ticket PDFs, payment failures, refunds, and event-cancellation messages.
- F12: assigned seat holds/race/checkout, folded/escaped ICS and calendar links,
  private normalized support screenshots and note visibility all implemented
  and covered by regression tests. React exposes these workflows.

Final automated evidence:

- **703 backend tests passed** on Docker/PostgreSQL 16.
- **18 frontend tests passed** (client/session and DOM workflow tests).
- **17 Flutter tests passed** against the final OpenAPI contract.
- Backend Ruff lint/format, frontend lint and production build passed.
- Generated OpenAPI matches current code: **121 paths**.
- Docker backend and production web builds passed. New CI jobs cover web and
  Flutter; remote CI acceptance requires committing/pushing these local changes.
- Preview: http://localhost:55173 ; API: http://localhost:58000 ; Mailpit:
  http://localhost:58025 . Dedicated Compose project: `biletflow-rehearsal`;
  database: `biletflow_demo`. Ignored `.env` holds the local port configuration.

## Remaining acceptance work

- Visual browser review completed through native Chrome controls on 2026-11-13:
  desktop discovery, attendee/organizer/admin sign-in and sign-out, ticket QR and
  actual PDF download, event editing, analytics and admin users. A 390×844
  responsive check confirmed workspace links remain accessible in the new menu.
  Fixed and regression-tested delayed select options preserving saved venue,
  mobile navigation, and table action-cell alignment. See
  `docs/acceptance-2026-11-13.md`.
- Physical Flutter camera/printed-ticket test on a real device; use the manual
  checklist in `docs/demo-flow.md`. No device was available to the agent.
- Jira triage board: requires the team's project/access. A local integration bug
  template is ready at `.github/ISSUE_TEMPLATE/integration_bug.yml`; no external
  project, board, messages or issues were created.
- Review branch publication and remote CI verification are in progress.

## Completion rules

Use `Implemented; verification pending` when tooling prevents execution. Record
remaining gaps explicitly. Run relevant checks after each step; run the full
backend suite and OpenAPI drift check after backend changes. Keep credentials,
issued PDFs, QR images, database files, and local runtime artifacts out of Git.
