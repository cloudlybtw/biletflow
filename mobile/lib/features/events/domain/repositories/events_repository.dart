import 'package:biletflow_verify/features/events/domain/entities/event_entities.dart';

abstract interface class EventsRepository {
  Future<List<AssignedEvent>> getAssignedEvents();
  Future<AttendanceStats> getAttendanceStats(String eventId);
}