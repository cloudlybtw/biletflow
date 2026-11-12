import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/network/dio_client.dart';
import 'package:biletflow_verify/features/check_in/data/datasources/check_in_remote_data_source.dart';
import 'package:biletflow_verify/features/check_in/data/repositories/check_in_repository_impl.dart';
import 'package:biletflow_verify/features/check_in/domain/repositories/check_in_repository.dart';
import 'package:biletflow_verify/features/check_in/domain/usecases/check_in_usecases.dart';

final checkInRemoteDataSourceProvider =
    Provider((ref) => CheckInRemoteDataSource(ref.watch(dioProvider)));

final checkInRepositoryProvider = Provider<CheckInRepository>(
  (ref) => CheckInRepositoryImpl(ref.watch(checkInRemoteDataSourceProvider)),
);

final validateTicketScanProvider =
    Provider((ref) => ValidateTicketScan(ref.watch(checkInRepositoryProvider)));
final manualCheckInProvider =
    Provider((ref) => ManualCheckIn(ref.watch(checkInRepositoryProvider)));
final reverseCheckInProvider =
    Provider((ref) => ReverseCheckIn(ref.watch(checkInRepositoryProvider)));
final searchAttendeesProvider =
    Provider((ref) => SearchAttendees(ref.watch(checkInRepositoryProvider)));