import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/network/api_error_mapper.dart';
import 'package:biletflow_verify/core/network/auth_interceptor.dart';
import 'package:biletflow_verify/core/network/pagination.dart';
import 'package:biletflow_verify/core/storage/token_storage.dart';
import 'package:biletflow_verify/features/auth/data/auth_repository.dart';
import 'package:biletflow_verify/features/check_in/data/datasources/check_in_remote_data_source.dart';
import 'package:biletflow_verify/features/check_in/data/repositories/check_in_repository_impl.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';
import 'package:biletflow_verify/features/events/data/datasources/events_remote_data_source.dart';

class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handle);
  final (Object?, int) Function(RequestOptions) handle;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final (body, status) = handle(options);
    return ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Dio client((Object?, int) Function(RequestOptions) handle) =>
    Dio(BaseOptions(baseUrl: 'http://test'))
      ..httpClientAdapter = FakeAdapter(handle);

Map<String, dynamic> ticket() => {
  'ticket_id': 'ticket-1',
  'ticket_code': 'BF123',
  'attendee_name': 'Dana',
  'attendee_email': 'dana@example.com',
  'ticket_type_id': 'type-1',
  'ticket_type_name': 'General',
  'status': 'checked_in',
  'checked_in_at': '2026-11-12T10:00:00Z',
  'seat_section_label': null,
  'seat_row_label': null,
  'seat_number_label': null,
  'check_in_record_id': 'record-1',
};
Map<String, dynamic> verdict(String result) => {
  'record_id': 'record-1',
  'event_id': 'event-1',
  'action': 'check_in',
  'result': result,
  'source': 'qr_scan',
  'scanned_at': '2026-11-12T10:00:00Z',
  'reverses_record_id': null,
  'ticket': result == 'valid' ? ticket() : null,
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('mobile paths and verdicts exist in the committed OpenAPI contract', () {
    final schema =
        jsonDecode(File('../docs/openapi.json').readAsStringSync()) as Map;
    final paths = schema['paths'] as Map;
    for (final path in [
      '/api/v1/auth/login',
      '/api/v1/auth/refresh',
      '/api/v1/auth/logout',
      '/api/v1/me',
      '/api/v1/events/assigned',
      '/api/v1/checkin/scan',
      '/api/v1/events/{event_id}/checkin/attendees',
      '/api/v1/events/{event_id}/checkin/counters',
      '/api/v1/events/{event_id}/checkin/records/{record_id}/reverse',
    ]) {
      expect(paths.containsKey(path), isTrue, reason: path);
    }
    final components = schema['components']['schemas'] as Map;
    expect(
      components['CheckInResult']['enum'],
      containsAll([
        'valid',
        'duplicate',
        'campaign_code_rejected',
        'wrong_event',
        'refunded',
      ]),
    );
    expect(
      components['ScanIn']['properties'].keys,
      containsAll(['token', 'ticket_id']),
    );
    expect(
      components['CheckInOut']['properties'].keys,
      containsAll(['record_id', 'ticket']),
    );
  });

  test(
    'scan sends token/event query and reads nested ticket with undo record',
    () async {
      final dio = client((request) {
        expect(request.path, '/api/v1/checkin/scan');
        expect(request.queryParameters, {'event_id': 'event-1'});
        expect(
          (request.data is String
              ? jsonDecode(request.data as String)
              : request.data),
          {'token': 'bft_123'},
        );
        return (verdict('valid'), 201);
      });
      final repo = CheckInRepositoryImpl(CheckInRemoteDataSource(dio));
      final outcome = await repo.submitScan(
        eventId: 'event-1',
        qrPayload: 'bft_123',
      );
      expect(outcome.admitted, isTrue);
      expect(outcome.canUndo, isTrue);
      expect(outcome.checkInId, 'record-1');
      expect(outcome.ticketId, 'ticket-1');
      expect(outcome.attendeeName, 'Dana');
      expect(outcome.ticketTypeName, 'General');
    },
  );

  for (final entry in {
    'duplicate': ScanVerdict.alreadyUsed,
    'cancelled': ScanVerdict.cancelled,
    'refunded': ScanVerdict.refunded,
    'invalid': ScanVerdict.invalid,
    'wrong_event': ScanVerdict.wrongEvent,
    'campaign_code_rejected': ScanVerdict.campaignQr,
    'future_unknown_result': ScanVerdict.invalid,
  }.entries) {
    test('${entry.key} never admits', () async {
      final repo = CheckInRepositoryImpl(
        CheckInRemoteDataSource(client((_) => (verdict(entry.key), 201))),
      );
      final outcome = await repo.submitScan(
        eventId: 'event-1',
        qrPayload: 'bft_123',
      );
      expect(outcome.verdict, entry.value);
      expect(outcome.admitted, isFalse);
      expect(outcome.canUndo, isFalse);
    });
  }

  test('manual check-in and reverse use ticket_id and notes', () async {
    final dio = client((request) {
      if (request.path.endsWith('/reverse')) {
        expect(
          request.path,
          '/api/v1/events/event-1/checkin/records/record-1/reverse',
        );
        expect(
          (request.data is String
              ? jsonDecode(request.data as String)
              : request.data),
          {'notes': 'Accidental scan'},
        );
      } else {
        expect(request.path, '/api/v1/checkin/scan');
        expect(request.queryParameters['event_id'], 'event-1');
        expect(
          (request.data is String
              ? jsonDecode(request.data as String)
              : request.data),
          {'ticket_id': 'ticket-1'},
        );
      }
      return (verdict('valid'), 201);
    });
    final repo = CheckInRepositoryImpl(CheckInRemoteDataSource(dio));
    expect(
      (await repo.manualCheckIn(
        eventId: 'event-1',
        ticketId: 'ticket-1',
      )).admitted,
      isTrue,
    );
    await repo.reverseCheckIn(
      eventId: 'event-1',
      checkInId: 'record-1',
      reason: 'Accidental scan',
    );
  });

  test(
    'attendee search fetches every page and decodes attendee names',
    () async {
      final offsets = <int>[];
      final dio = client((request) {
        expect(request.path, '/api/v1/events/event-1/checkin/attendees');
        expect(request.queryParameters['q'], 'Dana');
        final offset = request.queryParameters['offset'] as int;
        offsets.add(offset);
        return (
          {
            'items': List.generate(offset == 0 ? 100 : 1, (_) => ticket()),
            'total': 101,
          },
          200,
        );
      });
      final repo = CheckInRepositoryImpl(CheckInRemoteDataSource(dio));
      final matches = await repo.searchAttendees(
        eventId: 'event-1',
        query: 'Dana',
      );
      expect(matches.length, 101);
      expect(matches.last.fullName, 'Dana');
      expect(offsets, [0, 100]);
    },
  );

  test('assigned events and counters use backend contract', () async {
    final remote = EventsRemoteDataSource(
      client((request) {
        if (request.path.endsWith('/counters')) {
          expect(request.path, '/api/v1/events/event-1/checkin/counters');
          return ({'registered': 12, 'checked_in': 3}, 200);
        }
        expect(request.path, '/api/v1/events/assigned');
        return (
          {
            'items': [
              {
                'id': 'event-1',
                'title': 'Demo',
                'starts_at': '2026-11-13T10:00:00Z',
                'ends_at': '2026-11-13T12:00:00Z',
                'timezone': 'Asia/Almaty',
              },
            ],
            'total': 1,
          },
          200,
        );
      }),
    );
    expect((await remote.fetchAssignedEvents()).single.title, 'Demo');
    final counters = await remote.fetchCheckInSummary('event-1');
    expect(counters.registeredCount, 12);
    expect(counters.checkedInCount, 3);
  });

  test('malformed pages fail rather than show an empty event list', () {
    expect(() => decodePage({'unexpected': []}), throwsFormatException);
  });

  test('backend error envelope is shown to the user', () {
    final error = parseApiError({
      'error': {
        'code': 'ACCOUNT_SUSPENDED',
        'message': 'Account suspended.',
        'details': {},
      },
    });
    expect(error.code, 'ACCOUNT_SUSPENDED');
    expect(error.message, 'Account suspended.');
  });

  test('network errors and incomplete valid responses never admit', () async {
    final repo = CheckInRepositoryImpl(
      CheckInRemoteDataSource(client((_) => ({'result': 'valid'}, 200))),
    );
    await expectLater(
      repo.submitScan(eventId: 'event-1', qrPayload: 'bft_x'),
      throwsA(isA<ServerFailure>()),
    );
    final missingTicket = CheckInRepositoryImpl(
      CheckInRemoteDataSource(
        client((_) => ({...verdict('valid'), 'ticket': null}, 201)),
      ),
    );
    await expectLater(
      missingTicket.submitScan(eventId: 'event-1', qrPayload: 'bft_x'),
      throwsA(isA<ServerFailure>()),
    );
    final wrongEvent = CheckInRepositoryImpl(
      CheckInRemoteDataSource(
        client((_) => ({...verdict('valid'), 'event_id': 'other-event'}, 201)),
      ),
    );
    await expectLater(
      wrongEvent.submitScan(eventId: 'event-1', qrPayload: 'bft_x'),
      throwsA(isA<ServerFailure>()),
    );
    final httpError = CheckInRepositoryImpl(
      CheckInRemoteDataSource(client((_) => (verdict('valid'), 400))),
    );
    await expectLater(
      httpError.submitScan(eventId: 'event-1', qrPayload: 'bft_x'),
      throwsA(isA<ServerFailure>()),
    );
    final denied = CheckInRepositoryImpl(
      CheckInRemoteDataSource(
        client(
          (_) => (
            {
              'error': {'code': 'FORBIDDEN', 'message': 'Access denied.'},
            },
            403,
          ),
        ),
      ),
    );
    await expectLater(
      denied.submitScan(eventId: 'event-1', qrPayload: 'bft_x'),
      throwsA(isA<ForbiddenFailure>()),
    );
  });

  test(
    'auth persists rotating tokens, restores /me, and revokes logout',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      final storage = TokenStorage(const FlutterSecureStorage());
      var refreshed = false;
      final dio = client((request) {
        final body = request.data is String
            ? jsonDecode(request.data as String)
            : request.data;
        switch (request.path) {
          case '/api/v1/auth/login':
            expect(body, {'email': 'dana@example.com', 'password': 'password'});
            return (
              {
                'access_token': 'old',
                'refresh_token': 'refresh-1',
                'user': {
                  'id': 'u1',
                  'full_name': 'Dana',
                  'email': 'dana@example.com',
                },
              },
              200,
            );
          case '/api/v1/auth/refresh':
            expect(body, {'refresh_token': 'refresh-1'});
            refreshed = true;
            return ({'access_token': 'new', 'refresh_token': 'refresh-2'}, 200);
          case '/api/v1/me':
            if (request.headers['Authorization'] == 'Bearer old') {
              return ({}, 401);
            }
            expect(request.headers['Authorization'], 'Bearer new');
            return (
              {'id': 'u1', 'full_name': 'Dana', 'email': 'dana@example.com'},
              200,
            );
          case '/api/v1/auth/logout':
            expect(body, {'refresh_token': 'refresh-2'});
            return (null, 204);
        }
        throw StateError('Unexpected request ${request.path}');
      });
      final retry = Dio(dio.options)..httpClientAdapter = dio.httpClientAdapter;
      dio.interceptors.add(
        AuthInterceptor(
          tokens: storage,
          retryClient: retry,
          onSessionExpired: () => fail('Unexpected expiry'),
        ),
      );
      final auth = AuthRepository(dio, storage);
      expect(
        (await auth.signIn(
          email: ' dana@example.com ',
          password: 'password',
        )).id,
        'u1',
      );
      expect(await storage.accessToken(), 'old');
      expect((await auth.restore())?.fullName, 'Dana');
      expect(refreshed, isTrue);
      expect(await storage.refreshToken(), 'refresh-2');
      await auth.signOut();
      expect(await storage.accessToken(), isNull);
      expect(await storage.refreshToken(), isNull);
    },
  );

  test('failed server logout still clears local tokens', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final storage = TokenStorage(const FlutterSecureStorage());
    await storage.save(accessToken: 'access', refreshToken: 'refresh');
    final auth = AuthRepository(client((_) => ({}, 500)), storage);
    await expectLater(auth.signOut(), throwsA(isA<ServerFailure>()));
    expect(await storage.accessToken(), isNull);
    expect(await storage.refreshToken(), isNull);
  });
}
