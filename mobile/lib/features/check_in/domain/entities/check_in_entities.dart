/// Every possible answer to "may this person enter?".
enum ScanVerdict { valid, alreadyUsed, cancelled, refunded, invalid, wrongEvent, campaignQr }

class ScanOutcome {

  const ScanOutcome({
    required this.verdict,
    this.checkInId,
    this.ticketId,
    this.attendeeName,
    this.ticketTypeName,
    this.checkedInAt,
    this.serverMessage,
    this.decidedOnDevice = false,
  });


  final ScanVerdict verdict;

 
  final String? checkInId;
  final String? ticketId;
  final String? attendeeName;
  final String? ticketTypeName;

  
  final DateTime? checkedInAt;
  final String? serverMessage;

  
  final bool decidedOnDevice;

  bool get admitted => verdict == ScanVerdict.valid;
  bool get canUndo => admitted && checkInId != null;
}












enum TicketStatus { valid, checkedIn, cancelled, refunded, unknown }


class AttendeeMatch {
  const AttendeeMatch({
    required this.ticketId,
    required this.fullName,
    required this.status,
    this.email,
    this.orderId,
    this.ticketTypeName,
    this.checkedInAt,
  });
  

  final String ticketId;
  final String fullName;
  final TicketStatus status;
  final String? email;
  final String? orderId;
  final String? ticketTypeName;
  final DateTime? checkedInAt;
}