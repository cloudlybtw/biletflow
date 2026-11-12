/// Paths follow the committed docs/openapi.json contract.
abstract final class ApiEndpoints {
  static const _v1 = '/api/v1';
  static const login = '$_v1/auth/login';
  static const refresh = '$_v1/auth/refresh';
  static const logout = '$_v1/auth/logout';
  static const me = '$_v1/me';
  static const assignedEvents = '$_v1/events/assigned';
  static const scanCheckIn = '$_v1/checkin/scan';

  static String checkInSummary(String eventId) =>
      '$_v1/events/$eventId/checkin/counters';
  static String reverseCheckIn(String eventId, String checkInId) =>
      '$_v1/events/$eventId/checkin/records/$checkInId/reverse';
  static String searchAttendees(String eventId) =>
      '$_v1/events/$eventId/checkin/attendees';
}
