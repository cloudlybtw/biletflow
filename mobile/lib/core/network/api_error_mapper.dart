import 'package:dio/dio.dart';

import 'package:biletflow_verify/core/error/failure.dart';

typedef ApiErrorBody = ({String? code, String? message});

ApiErrorBody parseApiError(Object? data) {
  if (data is! Map) return (code: null, message: null);
  final error = data['error'];
  if (error is Map) {
    return (code: _str(error['code']), message: _str(error['message']));
  }
  final detail = data['detail'];
  return switch (detail) {
    String text => (code: null, message: text),
    Map map => (
      code: _str(map['code']),
      message: _str(map['message']) ?? _str(map['msg']),
    ),
    [Map first, ...] => (code: 'validation_error', message: _str(first['msg'])),
    _ => (code: _str(data['code']), message: _str(data['message'])),
  };
}

String? _str(Object? value) =>
    value is String && value.isNotEmpty ? value : null;

Failure mapDioException(DioException e) => switch (e.type) {
  DioExceptionType.connectionTimeout ||
  DioExceptionType.sendTimeout ||
  DioExceptionType.receiveTimeout ||
  DioExceptionType.transformTimeout => const TimeoutFailure(),

  DioExceptionType.badResponse => _fromStatus(e.response),

  DioExceptionType.badCertificate => const NetworkFailure(
    'Could not establish a secure connection to the server.',
  ),

  DioExceptionType.cancel => const NetworkFailure('The request was cancelled.'),
  _ => const NetworkFailure(),
};

Failure _fromStatus(Response<dynamic>? response) {
  final status = response?.statusCode ?? 0;
  final message = parseApiError(response?.data).message;
  return switch (status) {
    401 =>
      message == null
          ? const UnauthorizedFailure()
          : UnauthorizedFailure(message),
    403 =>
      message == null ? const ForbiddenFailure() : ForbiddenFailure(message),
    422 => ValidationFailure(message ?? 'The server rejected the request.'),
    >= 500 => ServerFailure(
      'BiletFlow server error ($status). Please try again.',
      statusCode: status,
    ),
    _ => ServerFailure(
      message ?? 'Unexpected server response ($status).',
      statusCode: status,
    ),
  };
}
