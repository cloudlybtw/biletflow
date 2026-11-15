# Final acceptance handoff

Code completion is separate from device and deployment acceptance. The current
remaining external prerequisites are a supported camera phone, uninterrupted
browser/screen-reader review, a backend/database deployment host and the team's
Jira destination. Do not mark the checks below complete from unit tests.

## Accessibility

Use a dedicated demo account and the seeded local deployment. For kk and ru,
complete event discovery → detail → checkout → payment → order → ticket → support
with Tab/Shift-Tab, Space and Enter. Verify names, prices, live feedback, focus
order and no keyboard trap. Test general admission and assigned seats. A disabled
seat belonging to another category must explain the matching ticket-type choice.
Submit a rejected form and verify focus reaches the error while values remain.

Repeat at narrow viewport and 200%, 300%, 400% zoom; record viewport/browser/
locale/revision. Whole-page horizontal scroll is a failure except genuinely
spatial seat layouts and data tables, which should scroll inside their named
regions. Inspect every error/focus/loading/empty state, not just the happy path.
Use VoiceOver/TalkBack for labels, controls, errors and status announcements.
Record measured foreground/background contrast for the rest of the interface.

Automated tests cover structural axe rules, explicit seat/error-state contrast,
form-error focus/value retention, skip navigation and locale switching. These
are evidence for those cases, not full WCAG conformance or manual completion.

## Native scanning

Follow `demo-flow.md` on a supported Android/iOS phone. Record permission denial,
retry/manual search, background/resume, digital/A4/grayscale QR scanning and the
valid/duplicate/wrong-event/cancelled/refunded/campaign rejection outcomes. Record
camera model, OS, build revision, network and print settings. The two-second
criterion requires actual online device timing, not the existing local API sample.

## Deployment prerequisites

The API/background worker, PostgreSQL and private uploads require an identified
runtime/storage destination. A frontend-only hosting choice is insufficient.
After the user chooses the target, follow `backup-recovery.md` to install the
daily timer, configure separate backup storage and alerts, then rehearse recovery
into isolated DB/media destinations. Do not perform a live restore as a drill.
Repeat representative paid-checkout and reporting-load measurements on that
actual topology using agreed service objectives. HTTPS/storage encryption remain
excluded until the user explicitly resumes M11.6.

Jira is still deferred until the team supplies its project and authorized access.
Local bug reports can use `.github/ISSUE_TEMPLATE/integration_bug.yml` meanwhile.
