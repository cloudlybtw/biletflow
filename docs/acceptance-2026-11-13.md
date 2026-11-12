# Browser acceptance — 2026-11-13

Reviewed the actual Docker/Nginx app at http://localhost:55173 using native
Google Chrome controls and screenshots. The browser automation host was
unavailable; native accessibility and screenshots worked. No browser password
was saved, and every demo session was signed out after review.

| Area             | Observed result                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------ |
| Public discovery | Both published seeded events rendered and navigation worked                                |
| Authentication   | Attendee, organizer and admin signed in; sign-out returned to login                        |
| Buyer tickets    | Real ticket statuses, attendee/type information, admission QR rendered                     |
| PDF              | Download A4 ticket produced a completed 33.4 KB PDF download in Chrome                     |
| Organizer        | Event list and management controls rendered live data                                      |
| Event editor     | Saved venue stayed selected after lookup options loaded, including reload                  |
| Analytics        | Seeded paid event showed 2 sold, 9,000 gross, 1,350 discounts, 7,650 net KZT, 1 checked in |
| Admin            | User search and four seeded users rendered with their roles/statuses                       |
| Responsive       | 390×844 viewport showed working Menu with account, organizer and admin destinations        |

## Fixes discovered during review

- Replaced uncontrolled select defaults with local controlled values so delayed
  option loading cannot silently clear a saved venue (or other selection).
- Added an accessible mobile workspace menu; desktop navigation had been hidden
  at mobile widths without a replacement.
- Kept table action layout inside the cell instead of making the cell flex.

Frontend lint/build and **18 client/DOM tests** pass after these fixes. The
browser review is representative acceptance, not a claim that every possible
role/state/browser combination has been manually exercised.

Chrome reported CSP blocks for external Google/Mathpix font/style requests.
Those resources are absent from the app's source; its fonts are served locally.
An Answer.AI extension was present in the page. The policy was retained; no
external font/style origin was allowlisted to accommodate injected resources.

## Still requires access or hardware

- Physical Flutter camera/printed-ticket acceptance. `flutter devices --machine`
  found macOS and Chrome only; there is no configured phone/simulator target.
- Jira board setup requires the Atlassian connection and destination project.
  An eligible Atlassian integration was found and offered for connection.
