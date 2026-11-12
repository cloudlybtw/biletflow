import 'dart:math' as math;

class AssignedEvent {

  const AssignedEvent({
    required this.id,
    required this.title,
    required this.startsAt,
    required this.endsAt,
    required this.timezone,
    this.venueName,
  });


  final String id;
  final String title;
  final DateTime startsAt;
  final DateTime endsAt;
  final String timezone;
  final String? venueName;

}

class AttendanceStats {

  const AttendanceStats({required this.registered, required this.checkedIn});

  final int registered;
  final int checkedIn;

  int get remaining => math.max(0, registered - checkedIn);
  double get progress => registered == 0 ? 0.0 : math.min(1.0, checkedIn / registered);

  
}