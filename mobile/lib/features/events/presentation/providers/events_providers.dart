import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/features/auth/presentation/providers/auth_controller.dart';
import 'package:biletflow_verify/features/events/di.dart';
import 'package:biletflow_verify/features/events/domain/entities/event_entities.dart';


final assignedEventsProvider = FutureProvider<List<AssignedEvent>>((ref) async {

  final userId = ref.watch(
    authControllerProvider.select((s) => s is AuthSignedIn ? s.user.id : null),
  );
  if (userId == null) return const [];
  return ref.watch(getAssignedEventsProvider).call();
});

final assignedEventProvider =
    FutureProvider.autoDispose.family<AssignedEvent, String>((ref, eventId) async {
  final events = await ref.watch(assignedEventsProvider.future);
  return events.firstWhere(
    (e) => e.id == eventId,
    orElse: () => throw const ForbiddenFailure('This event is not assigned to you.'),
  );
});


final attendanceStatsProvider =
    FutureProvider.autoDispose.family<AttendanceStats, String>((ref, eventId) {
  final poll = Timer(const Duration(seconds: 15), ref.invalidateSelf);
  ref.onDispose(poll.cancel);
  return ref.watch(getAttendanceStatsProvider).call(eventId);
});

