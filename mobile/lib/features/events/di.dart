import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:biletflow_verify/core/network/dio_client.dart';
import 'package:biletflow_verify/features/events/data/datasources/events_remote_data_source.dart';
import 'package:biletflow_verify/features/events/data/repositories/events_repository_impl.dart';
import 'package:biletflow_verify/features/events/domain/repositories/events_repository.dart';
import 'package:biletflow_verify/features/events/domain/usecases/events_usecases.dart';

final eventsRemoteDataSourceProvider =
    Provider((ref) => EventsRemoteDataSource(ref.watch(dioProvider)));

final eventsRepositoryProvider = Provider<EventsRepository>(
  (ref) => EventsRepositoryImpl(ref.watch(eventsRemoteDataSourceProvider)),
);

final getAssignedEventsProvider =
    Provider((ref) => GetAssignedEvents(ref.watch(eventsRepositoryProvider)));
final getAttendanceStatsProvider =
    Provider((ref) => GetAttendanceStats(ref.watch(eventsRepositoryProvider)));

