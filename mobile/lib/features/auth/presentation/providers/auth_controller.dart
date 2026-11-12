import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/network/dio_client.dart';
import 'package:biletflow_verify/features/auth/di.dart';
import 'package:biletflow_verify/features/auth/domain/entities/staff_user.dart';

sealed class AuthState {
  const AuthState();
}

final class AuthRestoring extends AuthState {
  const AuthRestoring();
}

final class AuthSignedOut extends AuthState {
  const AuthSignedOut({this.notice});
  final String? notice;
}

final class AuthSignedIn extends AuthState {
  const AuthSignedIn(this.user);
  final StaffUser user;
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(
  AuthController.new,
);

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    ref.listen<int>(sessionExpiredProvider, (previous, next) {
      if (state is AuthSignedIn) {
        state = const AuthSignedOut(
          notice: 'Your session expired. Please sign in again.',
        );
      }
    });
    Future.microtask(_restore);
    return const AuthRestoring();
  }

  Future<void> _restore() async {
    try {
      final user = await ref.read(restoreSessionProvider).call();
      state = user == null ? const AuthSignedOut() : AuthSignedIn(user);
    } on Failure catch (f) {
      state = AuthSignedOut(notice: f.message);
    }
  }

  Future<void> signIn({required String email, required String password}) async {
    final user = await ref
        .read(signInProvider)
        .call(email: email, password: password);
    state = AuthSignedIn(user);
  }

  Future<void> signOut() async {
    try {
      await ref.read(signOutProvider).call();
      state = const AuthSignedOut();
    } on Failure {
      state = const AuthSignedOut(
        notice:
            'Signed out on this device. Server logout could not be confirmed.',
      );
    }
  }
}

final loginControllerProvider =
    NotifierProvider.autoDispose<LoginController, AsyncValue<void>>(
      LoginController.new,
    );

class LoginController extends Notifier<AsyncValue<void>> {
  @override
  AsyncValue<void> build() => const AsyncData(null);

  Future<void> submit({required String email, required String password}) async {
    if (state.isLoading) return;
    state = const AsyncLoading();
    final result = await AsyncValue.guard(
      () => ref
          .read(authControllerProvider.notifier)
          .signIn(email: email, password: password),
    );
    if (ref.mounted) state = result;
  }
}
