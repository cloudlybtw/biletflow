import 'package:dio/dio.dart';
import 'package:biletflow_verify/core/network/api_endpoints.dart';
import 'package:biletflow_verify/core/network/pagination.dart';
import 'package:biletflow_verify/features/events/data/models/events_dtos.dart';

class EventsRemoteDataSource {
  const EventsRemoteDataSource(this._dio);
  final Dio _dio;

  Future<List<StaffEventDto>> fetchAssignedEvents() async {
    final items = await fetchAllPages(_dio, ApiEndpoints.assignedEvents);
    return items.map(StaffEventDto.fromJson).toList();
  }

  Future<CheckInSummaryDto> fetchCheckInSummary(String eventId) async {
    final res = await _dio.get<Map<String, dynamic>>(
      ApiEndpoints.checkInSummary(eventId),
    );
    return CheckInSummaryDto.fromJson(res.data!);
  }
}
