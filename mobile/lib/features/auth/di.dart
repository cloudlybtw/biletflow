import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/network/dio_client.dart';
import 'package:biletflow_verify/core/storage/token_storage.dart';
import 'package:biletflow_verify/features/auth/data/auth_repository.dart';
import 'package:biletflow_verify/features/auth/domain/entities/staff_user.dart';

final authRepositoryProvider = Provider(
  (ref) =>
      AuthRepository(ref.watch(dioProvider), ref.watch(tokenStorageProvider)),
);
final signInProvider = Provider(
  (ref) => SignIn(ref.watch(authRepositoryProvider)),
);
final restoreSessionProvider = Provider(
  (ref) => RestoreSession(ref.watch(authRepositoryProvider)),
);
final signOutProvider = Provider(
  (ref) => SignOut(ref.watch(authRepositoryProvider)),
);

class SignIn {
  const SignIn(this._repository);
  final AuthRepository _repository;
  Future<StaffUser> call({required String email, required String password}) =>
      _repository.signIn(email: email, password: password);
}

class RestoreSession {
  const RestoreSession(this._repository);
  final AuthRepository _repository;
  Future<StaffUser?> call() => _repository.restore();
}

class SignOut {
  const SignOut(this._repository);
  final AuthRepository _repository;
  Future<void> call() => _repository.signOut();
}
