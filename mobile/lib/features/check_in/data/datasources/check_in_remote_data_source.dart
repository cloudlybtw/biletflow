import 'package:dio/dio.dart';
import 'package:biletflow_verify/core/network/api_endpoints.dart';
import 'package:biletflow_verify/core/network/pagination.dart';
import 'package:biletflow_verify/features/check_in/data/models/check_in_dtos.dart';

class CheckInRemoteDataSource {
  const CheckInRemoteDataSource(this._dio);
  final Dio _dio;

  Future<ScanResponseDto> scan(String eventId, ScanRequestDto body) =>
      _postForVerdict(eventId, body.toJson());

  Future<ScanResponseDto> manualCheckIn(
    String eventId,
    ManualCheckInRequestDto body,
  ) => _postForVerdict(eventId, body.toJson());

  Future<void> reverse(
    String eventId,
    String checkInId,
    ReverseCheckInRequestDto body,
  ) async {
    await _dio.post<void>(
      ApiEndpoints.reverseCheckIn(eventId, checkInId),
      data: body.toJson(),
    );
  }

  Future<List<AttendeeSearchItemDto>> search(
    String eventId,
    String query,
  ) async {
    final items = await fetchAllPages(
      _dio,
      ApiEndpoints.searchAttendees(eventId),
      query: {'q': query},
    );
    return items.map(AttendeeSearchItemDto.fromJson).toList();
  }

  Future<ScanResponseDto> _postForVerdict(
    String eventId,
    Map<String, dynamic> body,
  ) async {
    final res = await _dio.post<Map<String, dynamic>>(
      ApiEndpoints.scanCheckIn,
      queryParameters: {'event_id': eventId},
      data: body,
    );
    return ScanResponseDto.fromJson(res.data!);
  }
}
