import 'package:dio/dio.dart';
import 'package:json_annotation/json_annotation.dart';

import 'package:biletflow_verify/core/network/api_error_mapper.dart';
import 'package:biletflow_verify/core/network/api_guard.dart';
import 'package:biletflow_verify/features/check_in/data/datasources/check_in_remote_data_source.dart';
import 'package:biletflow_verify/features/check_in/data/models/check_in_dtos.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';
import 'package:biletflow_verify/features/check_in/domain/repositories/check_in_repository.dart';

class CheckInRepositoryImpl implements CheckInRepository {
  const CheckInRepositoryImpl(this._remote);
  final CheckInRemoteDataSource _remote;

  @override
  Future<ScanOutcome> submitScan({required String eventId, required String qrPayload}) =>
      _decide(() => _remote.scan(eventId, ScanRequestDto(qrPayload: qrPayload)));

  @override
  Future<ScanOutcome> manualCheckIn({required String eventId, required String ticketId}) =>
      _decide(() => _remote.manualCheckIn(eventId, ManualCheckInRequestDto(ticketId: ticketId)));

  @override
  Future<void> reverseCheckIn({
    required String eventId,
    required String checkInId,
    required String reason,
  }) =>
      guardApi(
        () => _remote.reverse(eventId, checkInId, ReverseCheckInRequestDto(reason: reason)),
      );

  @override
  Future<List<AttendeeMatch>> searchAttendees({
    required String eventId,
    required String query,
  }) async {
    final items = await guardApi(() => _remote.search(eventId, query));
    return [for (final item in items) item.toDomain()];
  }


  Future<ScanOutcome> _decide(Future<ScanResponseDto> Function() call) async {
    try {
      return (await call()).toDomain();
    } on DioException catch (e) {
      final rejection = _rejectionFrom(e.response);
      if (rejection != null) return rejection;
      throw mapDioException(e);
    } on CheckedFromJsonException catch (e) {
      throw contractMismatch(e);
    }
  }

  ScanOutcome? _rejectionFrom(Response<dynamic>? response) {
    final status = response?.statusCode;
    if (response == null || status == null) return null;

    if (status < 400 || status >= 500 || status == 401 || status == 403) return null;

    final data = response.data;
    if (data is Map<String, dynamic> && data['result'] is String) {
      try {
        return ScanResponseDto.fromJson(data).toDomain();
      } on CheckedFromJsonException {
        return null;
      }
    }

    final (:code, :message) = parseApiError(data);
    final verdict = _verdictForErrorCode(code);
    return verdict == null ? null : ScanOutcome(verdict: verdict, serverMessage: message);
  }
}


ScanVerdict? _verdictForErrorCode(String? code) => switch (code) {
      'already_used' || 'already_checked_in' => ScanVerdict.alreadyUsed,
      'cancelled' || 'ticket_cancelled' => ScanVerdict.cancelled,
      'refunded' || 'ticket_refunded' => ScanVerdict.refunded,
      'wrong_event' => ScanVerdict.wrongEvent,
      'campaign_qr' || 'not_a_ticket' => ScanVerdict.campaignQr,
      'invalid' || 'invalid_qr' || 'invalid_signature' || 'ticket_not_found' =>
        ScanVerdict.invalid,
      _ => null,
    };

extension on ScanResponseDto {
  ScanOutcome toDomain() => ScanOutcome(
        verdict: switch (result) {
          ScanResultCodeDto.valid => ScanVerdict.valid,
          ScanResultCodeDto.alreadyUsed => ScanVerdict.alreadyUsed,
          ScanResultCodeDto.cancelled => ScanVerdict.cancelled,
          ScanResultCodeDto.refunded => ScanVerdict.refunded,
          ScanResultCodeDto.invalid => ScanVerdict.invalid,
          ScanResultCodeDto.wrongEvent => ScanVerdict.wrongEvent,
          ScanResultCodeDto.campaignQr => ScanVerdict.campaignQr,
          ScanResultCodeDto.unknown => ScanVerdict.invalid,
        },
        checkInId: checkInId,
        ticketId: ticketId,
        attendeeName: attendee?.fullName,
        ticketTypeName: ticketTypeName,
        checkedInAt: checkedInAt,
        serverMessage: message,
      );
}

extension on AttendeeSearchItemDto {
  AttendeeMatch toDomain() => AttendeeMatch(
        ticketId: ticketId,
        fullName: fullName,
        email: email,
        orderId: orderId,
        ticketTypeName: ticketTypeName,
        checkedInAt: checkedInAt,
        status: switch (status) {
          TicketStatusDto.valid => TicketStatus.valid,
          TicketStatusDto.checkedIn => TicketStatus.checkedIn,
          TicketStatusDto.cancelled => TicketStatus.cancelled,
          TicketStatusDto.refunded => TicketStatus.refunded,
          TicketStatusDto.unknown => TicketStatus.unknown,
        },
      );
}