abstract final class ApiEndpoints {
  
  static const _v1 = '/api/v1';


  static const login = '$_v1/auth/login';
  static const refresh = '$_v1/auth/refresh';
  static const me = '$_v1/auth/me';


  static const assignedEvents = '$_v1/staff/events';


  static String checkInSummary(String eventId) => '$_v1/events/$eventId/check-ins/summary';
  static String scanCheckIn(String eventId) => '$_v1/events/$eventId/check-ins/scan';
  static String manualCheckIn(String eventId) => '$_v1/events/$eventId/check-ins/manual';
  static String reverseCheckIn(String eventId, String checkInId) => '$_v1/events/$eventId/check-ins/$checkInId/reverse';
  static String searchAttendees(String eventId) => '$_v1/events/$eventId/check-ins/attendees';
}