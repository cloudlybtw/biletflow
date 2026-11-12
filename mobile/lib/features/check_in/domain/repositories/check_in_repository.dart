import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';

abstract interface class CheckInRepository {


  Future<ScanOutcome> submitScan({required String eventId, required String qrPayload});


  Future<ScanOutcome> manualCheckIn({required String eventId, required String ticketId});


  Future<void> reverseCheckIn
  ({
    required String eventId,
    required String checkInId,
    required String reason,
  });



  Future<List<AttendeeMatch>> searchAttendees({required String eventId, required String query});

  
}