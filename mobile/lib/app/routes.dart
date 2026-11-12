abstract final class AppRoutes {
  static const splash = '/splash';
  static const login = '/login';
  static const events = '/events';
  static String dashboard(String eventId) => '/events/$eventId';
  static String scan(String eventId) => '/events/$eventId/scan';
  static String search(String eventId) => '/events/$eventId/search';
}