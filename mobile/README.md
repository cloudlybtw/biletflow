# BiletFlow Verify (mobile)

Flutter app for event check-in staff: sign in, open an assigned event, scan
ticket QR codes, and check attendees in against the BiletFlow API.

## Run

CI uses Flutter **3.50.0** (Dart **3.14.0**). Use the same toolchain for a
reproducible dependency lock.

``` bash
flutter pub get
dart run build_runner build
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

API_BASE_URL: `10.0.2.2` from the Android emulator, `localhost` from the iOS
simulator, or the LAN IP of the machine running the API from a real phone.
Sign in with an account assigned to an event as check-in staff.

## Architecture

Clean Architecture per feature (`auth`, `events`, `check_in`):

- **domain**: entities, repository interfaces and use cases (pure Dart)
- **data**: freezed DTOs, Dio data sources and repository implementations
- **presentation**: Riverpod providers, screens and widgets

`core/` holds networking, token storage, errors and shared widgets. Each
feature's `di.dart` wires its layers together.

## Check-in safety rules

- The backend decides admission; the app never admits on its own.
- Campaign / link QR codes are rejected on the device and by the backend.
- Unknown results show INVALID; failed requests show NOT VERIFIED, never VALID.
- After 3.5 s the scanner says it is slow but keeps waiting, so a check-in is
  never left in an unknown state.

## API contract

Paths and DTOs follow [`docs/openapi.json`](../docs/openapi.json) and the
[Flutter integration guide](../docs/api-m6.md). Scan and manual admission share
`POST /api/v1/checkin/scan?event_id=…`; admission depends on the returned verdict,
not the HTTP status. See `test/api_contract_test.dart` for request/response,
pagination, refresh, and rejection regression tests.

Run code generation before `flutter analyze` and `flutter test`. Generated Dart
files are ignored; the auth source files are committed.

Flutter 3.50 reports existing Material imports as informational deprecations.
`--no-fatal-infos` preserves these diagnostics; analyzer errors and warnings
still fail CI. Migration to the new Material package is separate framework work.
