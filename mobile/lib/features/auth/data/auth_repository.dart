import 'package:dio/dio.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/network/api_endpoints.dart';
import 'package:biletflow_verify/core/network/api_guard.dart';
import 'package:biletflow_verify/core/network/auth_interceptor.dart';
import 'package:biletflow_verify/core/storage/token_storage.dart';
import 'package:biletflow_verify/features/auth/domain/entities/staff_user.dart';

class AuthRepository {
  const AuthRepository(this._dio, this._tokens);
  final Dio _dio;
  final TokenStorage _tokens;

  Future<StaffUser> signIn({required String email, required String password}) =>
      guardApi(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          ApiEndpoints.login,
          data: {'email': email.trim(), 'password': password},
          options: Options(extra: {AuthInterceptor.skipAuth: true}),
        );
        final body = response.data!;
        final user = StaffUser.fromJson(body['user'] as Map<String, dynamic>);
        await _tokens.save(
          accessToken: body['access_token'] as String,
          refreshToken: body['refresh_token'] as String,
        );
        return user;
      });

  Future<StaffUser?> restore() async {
    if (await _tokens.accessToken() == null) return null;
    try {
      return await guardApi(() async {
        final response = await _dio.get<Map<String, dynamic>>(ApiEndpoints.me);
        return StaffUser.fromJson(response.data!);
      });
    } on UnauthorizedFailure {
      await _tokens.clear();
      return null;
    }
  }

  Future<void> signOut() async {
    try {
      final token = await _tokens.refreshToken();
      if (token != null) {
        await guardApi(
          () => _dio.post<void>(
            ApiEndpoints.logout,
            data: {'refresh_token': token},
            options: Options(extra: {AuthInterceptor.skipAuth: true}),
          ),
        );
      }
    } finally {
      await _tokens.clear();
    }
  }
}
