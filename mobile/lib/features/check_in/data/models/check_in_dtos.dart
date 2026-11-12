import 'package:freezed_annotation/freezed_annotation.dart';
part 'check_in_dtos.freezed.dart';
part 'check_in_dtos.g.dart';

@freezed
abstract class ScanRequestDto with _$ScanRequestDto {
  const factory ScanRequestDto({
    @JsonKey(name: 'token') required String qrPayload,
  }) = _ScanRequestDto;
  factory ScanRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ScanRequestDtoFromJson(json);
}

@freezed
abstract class ManualCheckInRequestDto with _$ManualCheckInRequestDto {
  const factory ManualCheckInRequestDto({required String ticketId}) =
      _ManualCheckInRequestDto;
  factory ManualCheckInRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ManualCheckInRequestDtoFromJson(json);
}

@freezed
abstract class ReverseCheckInRequestDto with _$ReverseCheckInRequestDto {
  const factory ReverseCheckInRequestDto({
    @JsonKey(name: 'notes') required String reason,
  }) = _ReverseCheckInRequestDto;
  factory ReverseCheckInRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ReverseCheckInRequestDtoFromJson(json);
}

enum ScanResultCodeDto {
  @JsonValue('valid')
  valid,
  @JsonValue('duplicate')
  alreadyUsed,
  @JsonValue('cancelled')
  cancelled,
  @JsonValue('refunded')
  refunded,
  @JsonValue('invalid')
  invalid,
  @JsonValue('wrong_event')
  wrongEvent,
  @JsonValue('campaign_code_rejected')
  campaignQr,
  unknown,
}

@freezed
abstract class ScanResponseDto with _$ScanResponseDto {
  const factory ScanResponseDto({
    @JsonKey(unknownEnumValue: ScanResultCodeDto.unknown)
    required ScanResultCodeDto result,
    @JsonKey(name: 'record_id') required String checkInId,
    required String eventId,
    required String action,
    required DateTime scannedAt,
    AttendeeSearchItemDto? ticket,
  }) = _ScanResponseDto;
  factory ScanResponseDto.fromJson(Map<String, dynamic> json) =>
      _$ScanResponseDtoFromJson(json);
}

enum TicketStatusDto {
  @JsonValue('valid')
  valid,
  @JsonValue('checked_in')
  checkedIn,
  @JsonValue('cancelled')
  cancelled,
  @JsonValue('refunded')
  refunded,
  unknown,
}

@freezed
abstract class AttendeeSearchItemDto with _$AttendeeSearchItemDto {
  const factory AttendeeSearchItemDto({
    required String ticketId,
    @JsonKey(name: 'attendee_name') required String fullName,
    @JsonKey(name: 'attendee_email') String? email,
    String? ticketTypeName,
    @JsonKey(unknownEnumValue: TicketStatusDto.unknown)
    required TicketStatusDto status,
    DateTime? checkedInAt,
  }) = _AttendeeSearchItemDto;
  factory AttendeeSearchItemDto.fromJson(Map<String, dynamic> json) =>
      _$AttendeeSearchItemDtoFromJson(json);
}
