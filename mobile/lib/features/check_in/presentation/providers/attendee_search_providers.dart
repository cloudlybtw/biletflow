import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:biletflow_verify/features/check_in/di.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';

typedef AttendeeQuery = ({String eventId, String query});

final attendeeSearchProvider =
    FutureProvider.autoDispose.family<List<AttendeeMatch>, AttendeeQuery>(
  (ref, q) => ref.watch(searchAttendeesProvider).call(eventId: q.eventId, query: q.query),
);