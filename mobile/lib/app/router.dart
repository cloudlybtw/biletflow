import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:biletflow_verify/app/routes.dart';
import 'package:biletflow_verify/features/auth/presentation/providers/auth_controller.dart';
import 'package:biletflow_verify/features/auth/presentation/screens/login_screen.dart';
import 'package:biletflow_verify/features/check_in/presentation/screens/attendee_search_screen.dart';
import 'package:biletflow_verify/features/check_in/presentation/screens/scanner_screen.dart';
import 'package:biletflow_verify/features/events/presentation/screens/event_dashboard_screen.dart';
import 'package:biletflow_verify/features/events/presentation/screens/event_list_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {

  final auth = ValueNotifier<AuthState>(ref.read(authControllerProvider));
  ref.listen<AuthState>(authControllerProvider, (previous, next) => auth.value = next);

  final router = GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: auth,
    debugLogDiagnostics: kDebugMode,
    redirect: (context, state) {
      final location = state.matchedLocation;
      return switch (auth.value) {
        AuthRestoring() => location == AppRoutes.splash ? null : AppRoutes.splash,
        AuthSignedOut() => location == AppRoutes.login ? null : AppRoutes.login,
        AuthSignedIn() =>
          (location == AppRoutes.splash || location == AppRoutes.login) ? AppRoutes.events : null,
      };
    },
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (context, state) => const _SplashScreen()),
      GoRoute(path: AppRoutes.login, builder: (context, state) => const LoginScreen()),
      GoRoute(
        path: AppRoutes.events,
        builder: (context, state) => const EventListScreen(),
        routes: [
          GoRoute(
            path: ':eventId',
            builder: (context, state) =>
                EventDashboardScreen(eventId: state.pathParameters['eventId']!),
            routes: [
              GoRoute(
                path: 'scan',
                builder: (context, state) =>
                    ScannerScreen(eventId: state.pathParameters['eventId']!),
              ),
              GoRoute(
                path: 'search',
                builder: (context, state) =>
                    AttendeeSearchScreen(eventId: state.pathParameters['eventId']!),
              ),
            ],
          ),
        ],
      ),
    ],
  );

  ref.onDispose(() {
    router.dispose();
    auth.dispose();
  });
  return router;
});

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: CircularProgressIndicator()));
}