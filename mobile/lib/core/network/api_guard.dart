import 'package:dio/dio.dart';
import 'package:biletflow_verify/core/network/pagination.dart';
import 'package:json_annotation/json_annotation.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/network/api_error_mapper.dart';

Future<T> guardApi<T>(Future<T> Function() call) async {
  try {
    return await call();
  } on DioException catch (e) {
    throw mapDioException(e);
  } on CheckedFromJsonException catch (e) {
    throw contractMismatch(e);
  } on FormatException {
    throw const ServerFailure('Unexpected response from the server.');
  } on TypeError {
    throw const ServerFailure('Unexpected response from the server.');
  }
}

ServerFailure contractMismatch(CheckedFromJsonException e) => ServerFailure(
  'Unexpected response from the server (field "${e.key ?? '?'}"). '
  'The app and backend API contracts are out of sync.',
);

List<Map<String, dynamic>> unwrapList(Object? data) => decodePage(data).items;
