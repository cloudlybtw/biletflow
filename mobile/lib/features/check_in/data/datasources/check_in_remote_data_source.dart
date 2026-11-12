import 'package:dio/dio.dart';
import 'package:biletflow_verify/core/network/api_endpoints.dart';
import 'package:biletflow_verify/core/network/api_guard.dart';
import 'package:biletflow_verify/features/check_in/data/models/check_in_dtos.dart';

class CheckInRemoteDataSource {
  const CheckInRemoteDataSource(this._dio);
  final Dio _dio;

  Future<ScanResponseDto> scan(String eventId, ScanRequestDto body) =>
      _postForVerdict(ApiEndpoints.scanCheckIn(eventId), body.toJson());

  Future<ScanResponseDto> manualCheckIn(String eventId, ManualCheckInRequestDto body) =>
      _postForVerdict(ApiEndpoints.manualCheckIn(eventId), body.toJson());

  Future<void> reverse(String eventId, String checkInId, ReverseCheckInRequestDto body) async {
    await _dio.post<void>(ApiEndpoints.reverseCheckIn(eventId, checkInId), data: body.toJson());
  }

  Future<List<AttendeeSearchItemDto>> search(String eventId, String query) async {
    final res = await _dio.get<Object>(
      ApiEndpoints.searchAttendees(eventId),
      queryParameters: {'q': query},
    );
    return unwrapList(res.data).map(AttendeeSearchItemDto.fromJson).toList();
  }

  Future<ScanResponseDto> _postForVerdict(String path, Map<String, dynamic> body) async {
    final res = await _dio.post<Map<String, dynamic>>(path, data: body);
    return ScanResponseDto.fromJson(res.data!);
  }
}