import 'package:dio/dio.dart';
import 'package:biletflow_verify/core/network/api_endpoints.dart';
import 'package:biletflow_verify/core/storage/token_storage.dart';


class AuthInterceptor extends QueuedInterceptor {
  
  
  AuthInterceptor({
    required TokenStorage tokens,
    required Dio retryClient,
    required void Function() onSessionExpired,
  })  : _tokens = tokens,
        _retryClient = retryClient,
        _onSessionExpired = onSessionExpired;

  static const skipAuth = 'skip_auth';
  static const _retried = 'auth_retried';

  final TokenStorage _tokens;
  final Dio _retryClient;
  final void Function() _onSessionExpired;

  @override

  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    if (options.extra[skipAuth] != true) {
      final token = await _tokens.accessToken();
      if (token != null) options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override

  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    final request = err.requestOptions;
    final shouldRefresh = err.response?.statusCode == 401 &&
        request.extra[skipAuth] != true &&
        request.extra[_retried] != true;
    if (!shouldRefresh) return handler.next(err);


    final current = await _tokens.accessToken();
    final sentStaleToken = request.headers['Authorization'] != 'Bearer $current';
    final token = (current != null && sentStaleToken) ? current : await _refresh();

    if (token == null) {
      await _tokens.clear();
      _onSessionExpired();
      return handler.next(err);
    }

    request
      ..headers['Authorization'] = 'Bearer $token'
      ..extra[_retried] = true;
    try {
      handler.resolve(await _retryClient.fetch<dynamic>(request));
    } on DioException catch (e) {
      handler.next(e);
    }
  }



  Future<String?> _refresh() async {
    final refreshToken = await _tokens.refreshToken();
    if (refreshToken == null) return null;

    try 
    
    {
      final res = await _retryClient.post<Map<String, dynamic>>(
        ApiEndpoints.refresh,
        data: {'refresh_token': refreshToken},
      );
      final access = res.data?['access_token'];
      if (access is! String) return null;
      final rotated = res.data?['refresh_token'];
      await _tokens.save(accessToken: access, refreshToken: rotated is String ? rotated : null);
      return access;
    } 
    
    on DioException {
      return null;
    }


  }
}