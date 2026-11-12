import 'package:freezed_annotation/freezed_annotation.dart';
part 'events_dtos.freezed.dart';
part 'events_dtos.g.dart';

@freezed
abstract class StaffEventDto with _$StaffEventDto {
  const factory StaffEventDto({
    required String id,
    required String title,
    required DateTime startsAt,
    required DateTime endsAt,
    @Default('Asia/Almaty') String timezone,
    String? venueName,
  }) = _StaffEventDto;

  factory StaffEventDto.fromJson(Map<String, dynamic> json) =>
      _$StaffEventDtoFromJson(json);
}

@freezed
abstract class CheckInSummaryDto with _$CheckInSummaryDto {
  const factory CheckInSummaryDto({
    @JsonKey(name: 'registered') required int registeredCount,
    @JsonKey(name: 'checked_in') required int checkedInCount,
  }) = _CheckInSummaryDto;

  factory CheckInSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$CheckInSummaryDtoFromJson(json);
}
