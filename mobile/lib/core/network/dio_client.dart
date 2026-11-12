import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/config/env.dart';
import 'package:biletflow_verify/core/network/auth_interceptor.dart';
import 'package:biletflow_verify/core/storage/token_storage.dart';


final sessionExpiredProvider =
    NotifierProvider<SessionExpiredSignal, int>(SessionExpiredSignal.new);



class SessionExpiredSignal extends Notifier<int> {
  @override
  int build() => 0;

  void fire() => state++;
}



final dioProvider = Provider<Dio>((ref) {

  final options = BaseOptions(
    baseUrl: Env.apiBaseUrl,
    connectTimeout: const Duration(seconds: 5),
    sendTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 8),
    contentType: Headers.jsonContentType,
    headers: {'Accept': 'application/json'},
  );

  final dio = Dio(options)
    ..interceptors.add(
      AuthInterceptor(
        tokens: ref.watch(tokenStorageProvider),
        retryClient: Dio(options),
        onSessionExpired: () => ref.read(sessionExpiredProvider.notifier).fire(),
      ),
    );

  if (kDebugMode) {


    dio.interceptors.add(LogInterceptor(
      requestHeader: false,
      requestBody: false,
      responseHeader: false,
      responseBody: false,
    ));
  }

  
  return dio;
});