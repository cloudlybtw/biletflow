import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';
import 'package:biletflow_verify/features/check_in/domain/repositories/check_in_repository.dart';
import 'package:biletflow_verify/features/check_in/domain/services/qr_payload_classifier.dart';


class ValidateTicketScan {
  const ValidateTicketScan(this._repo);
  final CheckInRepository _repo;

  Future<ScanOutcome> call({required String eventId, required String rawPayload}) async {
    return switch (QrPayloadClassifier.classify(rawPayload)) {
    
      QrPayloadKind.campaignLink =>
        const ScanOutcome(verdict: ScanVerdict.campaignQr, decidedOnDevice: true),
      QrPayloadKind.unreadable =>
        const ScanOutcome(verdict: ScanVerdict.invalid, decidedOnDevice: true),
      QrPayloadKind.ticketCandidate =>
        await _repo.submitScan(eventId: eventId, qrPayload: rawPayload.trim()),

    };
  }
}

class ManualCheckIn {

  const ManualCheckIn(this._repo);
  final CheckInRepository _repo;

  Future<ScanOutcome> call({required String eventId, required String ticketId}) =>
      _repo.manualCheckIn(eventId: eventId, ticketId: ticketId);
}




class ReverseCheckIn {

  const ReverseCheckIn(this._repo);
  final CheckInRepository _repo;

  static const maxReasonLength = 200;

  Future<void> call({
    required String eventId,
    required String checkInId,
    required String reason,
  }) async {
    final trimmed = reason.trim();
    if (trimmed.isEmpty) {
      throw const ValidationFailure('Give a reason for undoing the check-in.');
    }
    if (trimmed.length > maxReasonLength) {
      throw const ValidationFailure('The reason is too long.');
    }
    await _repo.reverseCheckIn(eventId: eventId, checkInId: checkInId, reason: trimmed);
  }

}

class SearchAttendees {

  const SearchAttendees(this._repo);
  final CheckInRepository _repo;

  static const minQueryLength = 2;

  Future<List<AttendeeMatch>> call({required String eventId, required String query}) async {
    final q = query.trim();
    if (q.length < minQueryLength) return const [];
    return _repo.searchAttendees(eventId: eventId, query: q);
    
  }
}