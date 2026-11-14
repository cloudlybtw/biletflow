# M11 implementation and verification — 2026-11-14

M11.6 (hosting/TLS/encryption) was explicitly excluded. Nothing was deployed to
Cloudflare, Vercel or another public host. The original plan remains outside Git.

## Product workflows

- Customer locales: shared kk/ru/en selection across discovery, auth, checkout,
  account/tickets and support. Locale-aware dates/numbers, translated form/status
  labels, common API error codes and a localized fallback retaining unknown codes.
  Organizer/admin translations are not represented as fully complete. Backend
  email templates retain the plan's permitted English fallback. Organizer-supplied
  titles/descriptions and user messages are not machine-translated.
- Organizer figures: processing fees and estimated simulated payouts in analytics;
  authoritative per-ticket-type available/reserved/sold/refunded/cancelled/check-in
  counts through `/events/{id}/inventory`.
- Payouts: one simulated request per completed, uncancelled event, amount derived
  from authoritative analytics. Owner requests; platform admin moves requested →
  processing → paid/failed; failed can retry processing. Paid is terminal. Duplicate
  requests/transitions are idempotent, changed balances block processing/payment,
  and every change is audited and notifies the organizer in-app and by email.
  This does not transfer funds. Organizer event workspace has a payouts tab;
  platform admin has a payout queue.
- Reports: verified attendees can report visible events. Reports are private to
  the admin queue and progress from open/reviewing to resolved/dismissed; closed
  reports cannot reopen. Resolution notes and actor/timestamps are retained.
  Existing event/paid-sales suspension controls are available from report review.
- Support escalation: authorized support staff escalate unresolved cases with a
  reason; context/messages remain on the original case. Admin inbox filters
  `escalated=true`; admins can reply, assign and resolve. Admins retain read-only moderation until an attendee case is escalated. Requesters cannot escalate
  themselves or read internal notes. Escalation is audited and notifies admins
  and requester. Advanced disputes/chargebacks remain out of scope.

Apply `0008_operational_workflows` with the existing migration service before
running the new API. The additions preserve existing `/api/v1` routes and fields.
Regenerate `docs/openapi.json` after backend edits.

## Backups and recovery

See [backup-recovery.md](backup-recovery.md) and the daily systemd service/timer.
The schedule is ready to install on the deployment host; it is not installed on
this developer machine. Off-host storage, alert routing and recovery objectives
still require the eventual deployment's operator/configuration.

Rehearsed against the dedicated `biletflow-rehearsal` PostgreSQL 16 project:
checksum-validated dump plus actual normalized event image; isolated database and
separate media restore; restored image SHA-256 matches the original. An initial
isolated restore verified migration version 8, DB health, authenticated profile,
protected ticket details and generated PDF via ASGI, without starting an outbox
worker. No live DB or live uploads were overwritten.

## Accessibility

Added axe-core WCAG 2 A/AA and 2.1 AA structural checks for registration, login,
event detail and assigned-seat checkout in jsdom. These checks exclude color
contrast because jsdom has no layout engine. Added visible keyboard focus,
stronger control borders/text colors, responsive language controls, reduced-motion
support, translated accessible labels, document language/title and route-heading
focus. Native Chrome review confirmed sign-in form labels, button and language
selector render in its accessibility tree and screenshot. Browser automation host
was unavailable and native control later reported no available window, so manual
language switching, full keyboard traversal and mobile reflow were not signed off.

This is representative automated coverage plus fixes, not a full WCAG 2.1 AA
conformance claim. Remaining manual checks: VoiceOver/TalkBack announcements,
keyboard-only completion, 200–400% zoom/reflow, computed contrast over actual
backgrounds and the full range of error/seat states. No certificate or unsupported
claim of complete accessibility is implied.

## Mobile compatibility

Declared targets: Android 10/API 29+ and iOS 15+. Added explicit Android internet
and camera permissions, optional camera hardware (manual search remains usable),
and Android/iOS camera-denial widget tests verifying guidance, retry and manual
search. Existing iOS camera usage string remains configured. CI definitions now
include Android debug APK and macOS unsigned iOS builds; these new build jobs have
not been run remotely as part of this local change.

Local Android build attempt stopped because no Android SDK is installed. Local
iOS build requires the missing full Xcode installation. These build results remain
unverified until the prepared CI jobs run or the native tools are installed.

Physical device/printed-ticket acceptance remains deferred. A passing widget test
cannot verify camera autofocus, printed QR readability, device permission prompts
or public-network performance. Run `docs/demo-flow.md` on selected supported
Android/iOS devices before marking physical compatibility complete.

## Local performance rehearsal

Run against a dedicated seeded demo deployment:

```sh
cd backend
uv run python -m app.scripts.benchmark --base-url http://localhost:58000 --buyers 50
```

Measured Docker/PostgreSQL 16 on Linux aarch64, local HTTP, 50 concurrent free
checkouts, one buyer session, 20 analytics requests and 20 sequential QR scans:

| Workload | p50 ms | p95 ms | Maximum ms |
| --- | ---: | ---: | ---: |
| Checkout alone | 736.19 | 900.78 | 904.46 |
| Checkout with analytics | 599.05 | 784.78 | 794.18 |
| Analytics alongside checkout | 6.72 | 129.11 | 608.88 |
| Online QR admission API | 5.75 | 8.60 | 13.87 |

All 100 orders completed, reservations were cleared and inventory matched.
Mixed/baseline checkout p95 ratio was 0.871; no slowdown was observed in this
sample. Warmup/order effects mean this does not establish a general speedup or
production throughput SLA. Distinct-buyer/no-oversell contention remains covered
by the 50-buyers/10-tickets regression. Paid checkout is covered by functional
rehearsal/tests, not this free-checkout latency sample. QR timings exclude camera,
phone, TLS and public internet; the end-to-end two-second phone target is pending.


## Automated results

- Backend: **712 tests passed** on Docker/PostgreSQL 16, including new workflow
  permissions, notifications, audit entries, inventory and backup safety tests.
- Frontend: **22 tests passed**, including kk/ru rendering, localized errors,
  preserved form values on language change, admin payout submission and axe checks.
- Flutter: **19 tests passed**. Analyzer passed with zero errors/warnings;
  15 informational Material import deprecations remain.
- Ruff lint/format, frontend lint and production build passed. Generated OpenAPI
  contains **129 paths**. Migration round-trip coverage includes migration 0008.
- Native APK/iOS builds remain blocked locally as described above; prepared CI
  jobs have not run remotely. No changes were pushed or deployed in this task.
