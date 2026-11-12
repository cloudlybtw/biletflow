import 'package:biletflow_verify/features/events/domain/entities/event_entities.dart';
import 'package:biletflow_verify/features/events/domain/repositories/events_repository.dart';

class GetAssignedEvents {
  const GetAssignedEvents(this._repo);
  final EventsRepository _repo;

  Future<List<AssignedEvent>> call() => _repo.getAssignedEvents();
}

class GetAttendanceStats {
  const GetAttendanceStats(this._repo);
  final EventsRepository _repo;

  Future<AttendanceStats> call(String eventId) => _repo.getAttendanceStats(eventId);
}