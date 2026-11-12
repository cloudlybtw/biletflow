import 'package:biletflow_verify/core/network/api_guard.dart';
import 'package:biletflow_verify/features/events/data/datasources/events_remote_data_source.dart';
import 'package:biletflow_verify/features/events/data/models/events_dtos.dart';
import 'package:biletflow_verify/features/events/domain/entities/event_entities.dart';
import 'package:biletflow_verify/features/events/domain/repositories/events_repository.dart';

class EventsRepositoryImpl implements EventsRepository {
  const EventsRepositoryImpl(this._remote);
  final EventsRemoteDataSource _remote;

  @override
  Future<List<AssignedEvent>> getAssignedEvents() async {
    final dtos = await guardApi(_remote.fetchAssignedEvents);
    return [for (final dto in dtos) dto.toDomain()]
      ..sort((a, b) => a.startsAt.compareTo(b.startsAt));
  }

  @override
  Future<AttendanceStats> getAttendanceStats(String eventId) async {
    final dto = await guardApi(() => _remote.fetchCheckInSummary(eventId));
    return AttendanceStats(registered: dto.registeredCount, checkedIn: dto.checkedInCount);
  }
}

extension on StaffEventDto {
  AssignedEvent toDomain() => AssignedEvent(
        id: id,
        title: title,
        startsAt: startsAt,
        endsAt: endsAt,
        timezone: timezone,
        venueName: venueName,
      );
}