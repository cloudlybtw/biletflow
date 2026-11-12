import 'package:freezed_annotation/freezed_annotation.dart';
part 'check_in_dtos.freezed.dart';
part 'check_in_dtos.g.dart';


@freezed
abstract class ScanRequestDto with _$ScanRequestDto {
  const factory ScanRequestDto({required String qrPayload}) = _ScanRequestDto;

  factory ScanRequestDto.fromJson(Map<String, dynamic> json) => _$ScanRequestDtoFromJson(json);
}

@freezed
abstract class ManualCheckInRequestDto with _$ManualCheckInRequestDto {
  const factory ManualCheckInRequestDto({required String ticketId}) = _ManualCheckInRequestDto;

  factory ManualCheckInRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ManualCheckInRequestDtoFromJson(json);
}

@freezed
abstract class ReverseCheckInRequestDto with _$ReverseCheckInRequestDto {
  const factory ReverseCheckInRequestDto({required String reason}) = _ReverseCheckInRequestDto;

  factory ReverseCheckInRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ReverseCheckInRequestDtoFromJson(json);
}



enum ScanResultCodeDto {
  @JsonValue('valid')
  valid,
  @JsonValue('already_used')
  alreadyUsed,
  @JsonValue('cancelled')
  cancelled,
  @JsonValue('refunded')
  refunded,
  @JsonValue('invalid')
  invalid,
  @JsonValue('wrong_event')
  wrongEvent,
  @JsonValue('campaign_qr')
  campaignQr,
  unknown,
}


@freezed
abstract class AttendeeDto with _$AttendeeDto {
  const factory AttendeeDto({
    required String id,
    required String fullName,
    String? email,
    String? phone,
  }) = _AttendeeDto;

  factory AttendeeDto.fromJson(Map<String, dynamic> json) => _$AttendeeDtoFromJson(json);
}

@freezed
abstract class ScanResponseDto with _$ScanResponseDto {
  const factory ScanResponseDto({
    
    @JsonKey(unknownEnumValue: ScanResultCodeDto.unknown) required ScanResultCodeDto result,
    String? checkInId,
    String? ticketId,
    String? ticketTypeName,
    DateTime? checkedInAt,
    AttendeeDto? attendee,
    String? message,
  }) = _ScanResponseDto;

  factory ScanResponseDto.fromJson(Map<String, dynamic> json) => _$ScanResponseDtoFromJson(json);
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
    required String fullName,
    String? email,
    String? orderId,
    String? ticketTypeName,
    @JsonKey(unknownEnumValue: TicketStatusDto.unknown)
    @Default(TicketStatusDto.unknown)
    TicketStatusDto status,
    DateTime? checkedInAt,
  }) = _AttendeeSearchItemDto;

  factory AttendeeSearchItemDto.fromJson(Map<String, dynamic> json) =>
      _$AttendeeSearchItemDtoFromJson(json);
}