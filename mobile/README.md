# BiletFlow Verify (mobile)

Flutter app for event check-in staff: sign in, open an assigned event, scan
ticket QR codes, and check attendees in against the BiletFlow API.

## Run

``` bash
flutter pub get
dart run build_runner build --delete-conflicting-outputs
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
- After 2 s the scanner says it is slow but keeps waiting, so a check-in is
  never left in an unknown state.

## API contract

All paths are in `lib/core/network/api_endpoints.dart`. Items marked
`[VERIFY]` there and in the DTO files must be confirmed against
`docs/api-m6.md` or the backend's Swagger UI at `/docs`.
